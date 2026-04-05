"""
SQLite persistence layer for STRATUM.

Stores matters, documents, chunks (with embeddings), and contradictions
so that analysis results survive server restarts. FAISS indexes are
rebuilt from stored embedding vectors on startup.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "stratum.db"

_conn: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_db() -> None:
    """Create tables if they do not exist. Called once at startup."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS matters (
            matter_id TEXT PRIMARY KEY,
            entity_name TEXT NOT NULL DEFAULT '',
            acn TEXT NOT NULL DEFAULT '',
            graph_data_json TEXT,
            confirmed_flags_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            raw_text TEXT NOT NULL DEFAULT '',
            page_count INTEGER NOT NULL DEFAULT 0,
            sha256_hash TEXT NOT NULL DEFAULT '',
            entities_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
            matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
            doc_type TEXT NOT NULL,
            section_type TEXT NOT NULL DEFAULT 'general',
            page_number INTEGER NOT NULL DEFAULT 0,
            text_snippet TEXT NOT NULL DEFAULT '',
            embedding BLOB
        );

        CREATE TABLE IF NOT EXISTS contradictions (
            contradiction_id TEXT PRIMARY KEY,
            matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
            source_chunk_id TEXT,
            target_chunk_id TEXT,
            source_document TEXT NOT NULL DEFAULT '',
            source_doc_type TEXT NOT NULL DEFAULT '',
            source_section TEXT NOT NULL DEFAULT '',
            source_text TEXT NOT NULL DEFAULT '',
            target_document TEXT NOT NULL DEFAULT '',
            target_doc_type TEXT NOT NULL DEFAULT '',
            target_section TEXT NOT NULL DEFAULT '',
            target_text TEXT NOT NULL DEFAULT '',
            cosine_similarity REAL NOT NULL DEFAULT 0,
            cosine_distance REAL NOT NULL DEFAULT 0,
            typology_id TEXT NOT NULL DEFAULT '',
            typology_label TEXT NOT NULL DEFAULT '',
            typology_description TEXT NOT NULL DEFAULT '',
            typology_similarity REAL NOT NULL DEFAULT 0,
            severity TEXT NOT NULL DEFAULT 'medium',
            explanation TEXT NOT NULL DEFAULT '',
            confirmed INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_documents_matter ON documents(matter_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_matter ON chunks(matter_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_contradictions_matter ON contradictions(matter_id);
    """)
    conn.commit()
    logger.info("Database initialized at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Matters
# ---------------------------------------------------------------------------

def save_matter(matter_id: str, entity_name: str = "", acn: str = "",
                graph_data: Optional[dict] = None,
                confirmed_flags: Optional[list] = None) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO matters (matter_id, entity_name, acn, graph_data_json, confirmed_flags_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(matter_id) DO UPDATE SET
             entity_name = excluded.entity_name,
             acn = excluded.acn,
             graph_data_json = excluded.graph_data_json,
             confirmed_flags_json = excluded.confirmed_flags_json""",
        (matter_id, entity_name, acn,
         json.dumps(graph_data) if graph_data else None,
         json.dumps(confirmed_flags or []),
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def update_matter_graph(matter_id: str, graph_data: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE matters SET graph_data_json = ? WHERE matter_id = ?",
        (json.dumps(graph_data), matter_id),
    )
    conn.commit()


def update_matter_flags(matter_id: str, confirmed_flags: list) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE matters SET confirmed_flags_json = ? WHERE matter_id = ?",
        (json.dumps(confirmed_flags), matter_id),
    )
    conn.commit()


def db_get_matter(matter_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM matters WHERE matter_id = ?", (matter_id,)).fetchone()
    if not row:
        return None
    return {
        "matter_id": row["matter_id"],
        "entity_name": row["entity_name"],
        "acn": row["acn"],
        "graph_data": json.loads(row["graph_data_json"]) if row["graph_data_json"] else None,
        "confirmed_flags": json.loads(row["confirmed_flags_json"]) if row["confirmed_flags_json"] else [],
        "created_at": row["created_at"],
    }


def db_list_matters() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT m.matter_id, m.entity_name, m.acn, m.created_at, "
        "  (SELECT COUNT(*) FROM documents d WHERE d.matter_id = m.matter_id) as doc_count, "
        "  (SELECT COUNT(*) FROM contradictions c WHERE c.matter_id = m.matter_id) as contra_count "
        "FROM matters m ORDER BY m.created_at DESC"
    ).fetchall()
    return [
        {
            "matter_id": r["matter_id"],
            "entity_name": r["entity_name"],
            "acn": r["acn"],
            "document_count": r["doc_count"],
            "contradiction_count": r["contra_count"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def db_delete_matter(matter_id: str) -> bool:
    conn = get_connection()
    cursor = conn.execute("DELETE FROM matters WHERE matter_id = ?", (matter_id,))
    conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def save_document(document_id: str, matter_id: str, filename: str, doc_type: str,
                  raw_text: str = "", page_count: int = 0, sha256_hash: str = "",
                  entities_json: Optional[str] = None) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO documents (document_id, matter_id, filename, doc_type, raw_text, page_count, sha256_hash, entities_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(document_id) DO UPDATE SET
             entities_json = excluded.entities_json""",
        (document_id, matter_id, filename, doc_type, raw_text, page_count, sha256_hash,
         entities_json, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def update_document_entities(document_id: str, entities_json: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE documents SET entities_json = ? WHERE document_id = ?",
        (entities_json, document_id),
    )
    conn.commit()


def db_get_documents(matter_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM documents WHERE matter_id = ? ORDER BY created_at",
        (matter_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------

def save_chunk(chunk_id: str, document_id: str, matter_id: str, doc_type: str,
               section_type: str, page_number: int, text_snippet: str,
               embedding: np.ndarray) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO chunks
           (chunk_id, document_id, matter_id, doc_type, section_type, page_number, text_snippet, embedding)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (chunk_id, document_id, matter_id, doc_type, section_type, page_number, text_snippet,
         embedding.astype(np.float32).tobytes()),
    )
    conn.commit()


def db_get_chunks(matter_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chunks WHERE matter_id = ? ORDER BY rowid",
        (matter_id,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d["embedding"]:
            d["embedding"] = np.frombuffer(d["embedding"], dtype=np.float32)
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------

def save_contradiction(contradiction: dict) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO contradictions
           (contradiction_id, matter_id, source_chunk_id, target_chunk_id,
            source_document, source_doc_type, source_section, source_text,
            target_document, target_doc_type, target_section, target_text,
            cosine_similarity, cosine_distance, typology_id, typology_label,
            typology_description, typology_similarity, severity, explanation, confirmed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            contradiction.get("contradiction_id", ""),
            contradiction.get("matter_id", ""),
            contradiction.get("source_chunk_id", ""),
            contradiction.get("target_chunk_id", ""),
            contradiction.get("source_document", ""),
            contradiction.get("source_doc_type", ""),
            contradiction.get("source_section", ""),
            contradiction.get("source_text", ""),
            contradiction.get("target_document", ""),
            contradiction.get("target_doc_type", ""),
            contradiction.get("target_section", ""),
            contradiction.get("target_text", ""),
            contradiction.get("cosine_similarity", 0),
            contradiction.get("cosine_distance", 0),
            contradiction.get("typology_id", ""),
            contradiction.get("typology_label", ""),
            contradiction.get("typology_description", ""),
            contradiction.get("typology_similarity", 0),
            contradiction.get("severity", "medium"),
            contradiction.get("explanation", ""),
            1 if contradiction.get("confirmed") else 0,
        ),
    )
    conn.commit()


def db_get_contradictions(matter_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM contradictions WHERE matter_id = ? ORDER BY rowid",
        (matter_id,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["confirmed"] = bool(d["confirmed"])
        results.append(d)
    return results


def db_confirm_contradiction(contradiction_id: str) -> bool:
    conn = get_connection()
    cursor = conn.execute(
        "UPDATE contradictions SET confirmed = 1 WHERE contradiction_id = ?",
        (contradiction_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def clear_contradictions(matter_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM contradictions WHERE matter_id = ?", (matter_id,))
    conn.commit()
