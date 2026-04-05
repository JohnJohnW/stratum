"""
FastAPI application: Beneficial Ownership Contradiction Detector.

Endpoints for document upload, contradiction detection, graph retrieval,
CDD report generation, and demo fixture loading. WebSocket for real-time
graph and contradiction events.
"""

import asyncio
import logging
import os
import pathlib
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.cdd import generate_cdd_report
from backend.detection import run_contradiction_detection
from backend.documents import (
    DocumentType,
    create_matter,
    get_all_matters,
    get_matter,
    ingest_document,
    ingest_text_document,
)
from backend.fixtures import get_fixture_a, get_fixture_b
from backend.graph import build_fixture_graph
from backend.typologies import initialize_typology_index

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, matter_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(matter_id, []).append(ws)

    def disconnect(self, matter_id: str, ws: WebSocket):
        conns = self._connections.get(matter_id, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, matter_id: str, message: dict):
        dead = []
        for ws in self._connections.get(matter_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(matter_id, ws)


ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.database import init_db, db_list_matters, db_get_matter, db_get_chunks, db_get_contradictions, db_get_documents
    from backend.documents import load_matter_from_db

    # Initialize SQLite database
    init_db()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY not set. Demo and upload endpoints will fail. "
            "Set it in .env or environment variables."
        )
    else:
        logger.info("GEMINI_API_KEY is set. Initializing typology index...")
        try:
            await initialize_typology_index()
            logger.info("Typology index initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize typology index: %s", e)

    # Restore matters from SQLite
    existing = db_list_matters()
    for m in existing:
        mid = m["matter_id"]
        matter_data = db_get_matter(mid)
        chunks_data = db_get_chunks(mid)
        contras = db_get_contradictions(mid)
        docs_data = db_get_documents(mid)
        if matter_data:
            load_matter_from_db(matter_data, chunks_data or [], contras, docs_data)
    if existing:
        logger.info("Restored %d matter(s) from database.", len(existing))

    threshold = os.environ.get("CONTRADICTION_THRESHOLD", "0.65")
    logger.info("Contradiction threshold: %s", threshold)
    logger.info("STRATUM ready.")
    yield


app = FastAPI(
    title="BO Contradiction Detector",
    description="Beneficial Ownership Contradiction Detection for AML/CTF Tranche 2",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return RedirectResponse(url="/frontend/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/matters")
async def create_new_matter(entity_name: str = "", acn: str = ""):
    matter = create_matter(entity_name=entity_name, acn=acn)
    return {"matter_id": matter.matter_id, "entity_name": matter.entity_name, "acn": matter.acn}


@app.get("/matters")
async def list_matters():
    matters = get_all_matters()
    return [
        {
            "matter_id": m.matter_id,
            "entity_name": m.entity_name,
            "acn": m.acn,
            "document_count": len(m.documents),
            "contradiction_count": len(m.contradictions),
        }
        for m in matters
    ]


@app.get("/matters/{matter_id}")
async def get_matter_detail(matter_id: str):
    matter = get_matter(matter_id)
    if not matter:
        raise HTTPException(404, "Matter not found")
    return matter.model_dump()


@app.post("/upload/{doc_type}")
async def upload_document(
    doc_type: str,
    file: UploadFile = File(...),
    matter_id: str = "",
):
    try:
        dtype = DocumentType(doc_type)
    except ValueError:
        raise HTTPException(400, f"Invalid doc_type: {doc_type}. Must be one of: {[e.value for e in DocumentType]}")

    if not matter_id:
        matter = create_matter()
        matter_id = matter.matter_id
    elif not get_matter(matter_id):
        raise HTTPException(404, f"Matter {matter_id} not found")

    file_bytes = await file.read()
    doc = await ingest_document(matter_id, file_bytes, file.filename or "uploaded.pdf", dtype)

    await ws_manager.broadcast(matter_id, {
        "type": "status",
        "phase": "ingested",
        "message": f"Ingested {doc.filename} ({len(doc.chunks)} chunks)",
        "progress": 0.3,
    })

    return {
        "matter_id": matter_id,
        "document_id": doc.document_id,
        "filename": doc.filename,
        "doc_type": doc.doc_type.value,
        "chunks": len(doc.chunks),
        "pages": doc.page_count,
    }


@app.post("/matters/{matter_id}/detect")
async def detect_contradictions(matter_id: str):
    matter = get_matter(matter_id)
    if not matter:
        raise HTTPException(404, "Matter not found")

    await ws_manager.broadcast(matter_id, {
        "type": "status",
        "phase": "detecting",
        "message": "Running cross-document contradiction detection...",
        "progress": 0.6,
    })

    contradictions = await run_contradiction_detection(matter_id)

    for c in contradictions:
        await ws_manager.broadcast(matter_id, {
            "type": "contradiction_found",
            "contradiction": c.model_dump(),
        })

    return {
        "matter_id": matter_id,
        "contradictions_found": len(contradictions),
        "contradictions": [c.model_dump() for c in contradictions],
    }


@app.get("/matters/{matter_id}/graph")
async def get_graph(matter_id: str):
    matter = get_matter(matter_id)
    if not matter:
        raise HTTPException(404, "Matter not found")
    if matter.graph_data:
        return matter.graph_data
    raise HTTPException(404, "Graph not built yet. Run detection first or load a fixture.")


@app.get("/matters/{matter_id}/contradictions")
async def get_contradictions(matter_id: str):
    matter = get_matter(matter_id)
    if not matter:
        raise HTTPException(404, "Matter not found")
    return matter.contradictions


@app.post("/matters/{matter_id}/contradictions/{contradiction_id}/confirm")
async def confirm_contradiction(matter_id: str, contradiction_id: str):
    matter = get_matter(matter_id)
    if not matter:
        raise HTTPException(404, "Matter not found")

    for c in matter.contradictions:
        cid = c.get("contradiction_id") if isinstance(c, dict) else c.contradiction_id
        if cid == contradiction_id:
            if isinstance(c, dict):
                c["confirmed"] = True
            else:
                c.confirmed = True
            if contradiction_id not in matter.confirmed_flags:
                matter.confirmed_flags.append(contradiction_id)
            from backend.database import db_confirm_contradiction, update_matter_flags
            db_confirm_contradiction(contradiction_id)
            update_matter_flags(matter_id, matter.confirmed_flags)
            return {"status": "confirmed"}

    raise HTTPException(404, "Contradiction not found")


@app.post("/matters/{matter_id}/generate-cdd")
async def generate_cdd(matter_id: str):
    matter = get_matter(matter_id)
    if not matter:
        raise HTTPException(404, "Matter not found")

    pdf_bytes = await generate_cdd_report(matter_id)
    filename = f"CDD_Report_{matter.entity_name.replace(' ', '_')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/matters/{matter_id}")
async def delete_matter_endpoint(matter_id: str):
    from backend.documents import delete_matter
    if not get_matter(matter_id):
        raise HTTPException(404, "Matter not found")
    delete_matter(matter_id)
    return {"status": "deleted", "matter_id": matter_id}


@app.post("/matters/{matter_id}/analyse")
async def analyse_matter(matter_id: str):
    """Run the full analysis pipeline: extraction, detection, and graph building."""
    matter = get_matter(matter_id)
    if not matter:
        raise HTTPException(404, "Matter not found")

    if not matter.documents:
        raise HTTPException(400, "No documents uploaded. Upload at least 2 documents before running analysis.")

    await ws_manager.broadcast(matter_id, {
        "type": "status",
        "phase": "extracting",
        "message": "Extracting entities from documents...",
        "progress": 0.2,
    })

    # Run Gemini extraction on each document
    from backend.extraction import extract_entities
    from backend.database import update_document_entities
    entities_by_doc = {}
    for doc in matter.documents:
        try:
            entities = await extract_entities(doc.raw_text, doc.doc_type)
            entities_by_doc[doc.doc_type.value] = entities
            update_document_entities(doc.document_id, entities.model_dump_json())
            await ws_manager.broadcast(matter_id, {
                "type": "extraction_complete",
                "doc_type": doc.doc_type.value,
                "entities": entities.model_dump(),
            })
        except Exception as e:
            logger.warning("Extraction failed for %s: %s", doc.filename, e)

    await ws_manager.broadcast(matter_id, {
        "type": "status",
        "phase": "detecting",
        "message": "Running contradiction detection...",
        "progress": 0.5,
    })

    # Run contradiction detection
    contradictions = await run_contradiction_detection(matter_id)

    # Persist contradictions
    from backend.database import save_contradiction, clear_contradictions
    clear_contradictions(matter_id)
    for c in contradictions:
        save_contradiction(c.model_dump())
        await ws_manager.broadcast(matter_id, {
            "type": "contradiction_found",
            "contradiction": c.model_dump(),
        })

    await ws_manager.broadcast(matter_id, {
        "type": "status",
        "phase": "building_graph",
        "message": "Building ownership graph...",
        "progress": 0.75,
    })

    # Build graph from extracted entities if available, otherwise from regex
    from backend.graph import build_graph_from_entities, build_ownership_graph
    if entities_by_doc:
        graph_data = build_graph_from_entities(matter_id, entities_by_doc)
    else:
        graph_data = build_ownership_graph(matter_id)

    from backend.database import update_matter_graph
    update_matter_graph(matter_id, graph_data)

    await ws_manager.broadcast(matter_id, {
        "type": "graph_full",
        "data": graph_data,
    })

    await ws_manager.broadcast(matter_id, {
        "type": "status",
        "phase": "complete",
        "message": f"Analysis complete. {len(contradictions)} contradiction(s) found.",
        "progress": 1.0,
    })

    return {
        "matter_id": matter_id,
        "contradictions_found": len(contradictions),
        "contradictions": [c.model_dump() for c in contradictions],
    }


@app.get("/demo")
async def load_demo(fixture: str = "A"):
    fixture = fixture.upper()
    if fixture not in ("A", "B"):
        raise HTTPException(400, "fixture must be A or B")

    if fixture == "A":
        entity_info, documents = get_fixture_a()
    else:
        entity_info, documents = get_fixture_b()

    matter = create_matter(
        entity_name=entity_info["entity_name"],
        acn=entity_info["acn"],
    )
    mid = matter.matter_id

    # Broadcast: starting
    await ws_manager.broadcast(mid, {
        "type": "status",
        "phase": "ingesting",
        "message": f"Loading Fixture {fixture}...",
        "progress": 0.1,
    })

    # Ingest documents
    total_docs = len(documents)
    for i, (filename, doc_type, text, sections) in enumerate(documents):
        await ws_manager.broadcast(mid, {
            "type": "status",
            "phase": "embedding",
            "message": f"Embedding {filename}...",
            "progress": 0.1 + (0.4 * (i / total_docs)),
        })

        await ingest_text_document(
            matter_id=mid,
            text_content=text,
            filename=filename,
            doc_type=doc_type,
            sections=sections,
        )

        await ws_manager.broadcast(mid, {
            "type": "status",
            "phase": "ingested",
            "message": f"Ingested {filename}",
            "progress": 0.1 + (0.4 * ((i + 1) / total_docs)),
        })

    # Run detection
    await ws_manager.broadcast(mid, {
        "type": "status",
        "phase": "detecting",
        "message": "Running contradiction detection...",
        "progress": 0.55,
    })

    contradictions = await run_contradiction_detection(mid)

    # Persist contradictions
    from backend.database import save_contradiction as db_save_contra, clear_contradictions, update_matter_graph
    clear_contradictions(mid)
    for c in contradictions:
        db_save_contra(c.model_dump())
        await ws_manager.broadcast(mid, {
            "type": "contradiction_found",
            "contradiction": c.model_dump(),
        })

    # Build graph
    await ws_manager.broadcast(mid, {
        "type": "status",
        "phase": "building_graph",
        "message": "Building ownership graph...",
        "progress": 0.8,
    })

    graph_data = build_fixture_graph(mid, fixture)
    update_matter_graph(mid, graph_data)

    # Broadcast graph nodes and edges
    for node in graph_data.get("nodes", []):
        await ws_manager.broadcast(mid, {
            "type": "graph_update",
            "action": "add_node",
            "data": node,
        })
        await asyncio.sleep(0.05)  # small delay for animation

    for edge in graph_data.get("edges", []):
        await ws_manager.broadcast(mid, {
            "type": "graph_update",
            "action": "add_edge",
            "data": edge,
        })
        await asyncio.sleep(0.05)

    # Complete
    await ws_manager.broadcast(mid, {
        "type": "status",
        "phase": "complete",
        "message": f"Fixture {fixture} loaded. {len(contradictions)} contradiction(s) found.",
        "progress": 1.0,
    })

    return {
        "matter_id": mid,
        "fixture": fixture,
        "entity_name": entity_info["entity_name"],
        "documents_ingested": total_docs,
        "contradictions_found": len(contradictions),
        "contradictions": [c.model_dump() for c in contradictions],
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/{matter_id}")
async def websocket_endpoint(websocket: WebSocket, matter_id: str):
    await ws_manager.connect(matter_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "redetect":
                threshold = data.get("threshold")
                if threshold:
                    os.environ["CONTRADICTION_THRESHOLD"] = str(threshold)
                contradictions = await run_contradiction_detection(matter_id)
                for c in contradictions:
                    await websocket.send_json({
                        "type": "contradiction_found",
                        "contradiction": c.model_dump(),
                    })

            elif msg_type == "rebuild_graph":
                matter = get_matter(matter_id)
                if matter and matter.graph_data:
                    await websocket.send_json({
                        "type": "graph_full",
                        "data": matter.graph_data,
                    })

    except WebSocketDisconnect:
        ws_manager.disconnect(matter_id, websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        ws_manager.disconnect(matter_id, websocket)


# ---------------------------------------------------------------------------
# Static files: serve frontend
# ---------------------------------------------------------------------------

# Mount after all API routes so API routes take priority
_frontend_dir = pathlib.Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
