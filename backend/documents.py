"""
Document ingestion, preprocessing, and per-matter FAISS index management.

Handles PDF parsing (pdf2image + pdfplumber), embedding via Gemini Embedding 2,
and in-memory matter/document storage with FAISS vector indexes.
"""

import hashlib
import logging
import uuid
from enum import Enum
from io import BytesIO
from typing import Optional

import faiss
import numpy as np
from pydantic import BaseModel, Field

from backend.embeddings import EMBEDDING_DIM, embed_text, embed_multimodal

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    ASIC_EXTRACT = "asic_extract"
    CONSTITUTION = "constitution"
    SHAREHOLDER_REGISTER = "shareholder_register"


# Section types for structured embedding
ASIC_SECTIONS = [
    "officeholders", "share_structure", "registered_office", "ultimate_holding_company", "general"
]
CONSTITUTION_SECTIONS = [
    "objects_and_powers", "share_classes", "voting_rights", "quorum",
    "share_transfer_restrictions", "nominee_provisions", "director_appointment_removal", "general"
]
REGISTER_SECTIONS = ["shareholder_entry", "general"]


class DocumentChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    document_source: DocumentType
    section_type: str = "general"
    page_number: int = 0
    text_snippet: str = ""
    embedding_index: int = -1  # position in the matter's FAISS index


class Document(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    matter_id: str
    filename: str
    doc_type: DocumentType
    chunks: list[DocumentChunk] = []
    raw_text: str = ""
    page_count: int = 0
    sha256_hash: str = ""


class Matter(BaseModel):
    matter_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    acn: str = ""
    documents: list[Document] = []
    contradictions: list = []
    graph_data: dict = {}
    confirmed_flags: list[str] = []


# In-memory storage
_matters: dict[str, Matter] = {}
_doc_indexes: dict[str, faiss.IndexFlatIP] = {}
_doc_vectors: dict[str, list[np.ndarray]] = {}
_chunk_registry: dict[str, list[DocumentChunk]] = {}


def create_matter(entity_name: str = "", acn: str = "") -> Matter:
    """Create a new matter with an empty FAISS document index."""
    matter = Matter(entity_name=entity_name, acn=acn)
    mid = matter.matter_id
    _matters[mid] = matter
    _doc_indexes[mid] = faiss.IndexFlatIP(EMBEDDING_DIM)
    _doc_vectors[mid] = []
    _chunk_registry[mid] = []
    logger.info("Created matter %s: %s (ACN %s)", mid, entity_name, acn)
    return matter


def get_matter(matter_id: str) -> Optional[Matter]:
    return _matters.get(matter_id)


def get_all_matters() -> list[Matter]:
    return list(_matters.values())


def _add_vector_to_matter(matter_id: str, vector: np.ndarray, chunk: DocumentChunk) -> int:
    """Add a vector to the matter's FAISS index and return the index position."""
    idx = len(_chunk_registry[matter_id])
    chunk.embedding_index = idx
    _doc_vectors[matter_id].append(vector)
    _chunk_registry[matter_id].append(chunk)
    _doc_indexes[matter_id].add(vector.reshape(1, -1))
    return idx


def get_chunks_for_matter(matter_id: str) -> list[DocumentChunk]:
    return _chunk_registry.get(matter_id, [])


def get_vectors_for_matter(matter_id: str) -> Optional[np.ndarray]:
    vecs = _doc_vectors.get(matter_id, [])
    if not vecs:
        return None
    return np.array(vecs, dtype=np.float32)


def get_index_for_matter(matter_id: str) -> Optional[faiss.IndexFlatIP]:
    return _doc_indexes.get(matter_id)


async def ingest_document(
    matter_id: str,
    file_bytes: bytes,
    filename: str,
    doc_type: DocumentType,
) -> Document:
    """
    Full PDF ingestion pipeline:
    1. Render pages as images at 150 DPI
    2. Extract text per page
    3. Create multimodal embeddings (image + text interleaved)
    4. Store in matter's FAISS index
    """
    import pdfplumber
    from pdf2image import convert_from_bytes

    matter = _matters.get(matter_id)
    if not matter:
        raise ValueError(f"Matter {matter_id} not found")

    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Extract text
    text_pages = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text_pages.append(page.extract_text() or "")

    # Render pages as images
    images = convert_from_bytes(file_bytes, dpi=150, fmt="png")
    image_bytes_list = []
    for img in images:
        buf = BytesIO()
        img.save(buf, format="PNG")
        image_bytes_list.append(buf.getvalue())

    doc = Document(
        matter_id=matter_id,
        filename=filename,
        doc_type=doc_type,
        raw_text="\n\n".join(text_pages),
        page_count=len(text_pages),
        sha256_hash=sha256,
    )

    # Embed each page as multimodal (image + text)
    for page_num, (text, img_bytes) in enumerate(zip(text_pages, image_bytes_list)):
        section_type = _classify_section(text, doc_type)
        snippet = text[:500] if text else f"[Page {page_num + 1} image]"

        vec = await embed_multimodal(text or f"Page {page_num + 1}", img_bytes)

        chunk = DocumentChunk(
            document_id=doc.document_id,
            document_source=doc_type,
            section_type=section_type,
            page_number=page_num + 1,
            text_snippet=snippet,
        )
        _add_vector_to_matter(matter_id, vec, chunk)
        doc.chunks.append(chunk)

    matter.documents.append(doc)
    logger.info(
        "Ingested %s (%s): %d pages, %d chunks",
        filename, doc_type.value, doc.page_count, len(doc.chunks),
    )
    return doc


async def ingest_text_document(
    matter_id: str,
    text_content: str,
    filename: str,
    doc_type: DocumentType,
    sections: Optional[list[tuple[str, str]]] = None,
) -> Document:
    """
    Simplified ingestion for fixture/text data (no PDF rendering).

    Args:
        matter_id: The matter to add the document to.
        text_content: Full text of the document.
        filename: Display filename.
        doc_type: Document classification.
        sections: Optional list of (section_type, section_text) tuples.
                  If not provided, the full text is treated as a single chunk.
    """
    matter = _matters.get(matter_id)
    if not matter:
        raise ValueError(f"Matter {matter_id} not found")

    sha256 = hashlib.sha256(text_content.encode()).hexdigest()

    doc = Document(
        matter_id=matter_id,
        filename=filename,
        doc_type=doc_type,
        raw_text=text_content,
        page_count=1,
        sha256_hash=sha256,
    )

    if sections:
        for section_type, section_text in sections:
            vec = await embed_text(section_text)
            chunk = DocumentChunk(
                document_id=doc.document_id,
                document_source=doc_type,
                section_type=section_type,
                page_number=1,
                text_snippet=section_text[:800],
            )
            _add_vector_to_matter(matter_id, vec, chunk)
            doc.chunks.append(chunk)
    else:
        vec = await embed_text(text_content)
        section_type = _classify_section(text_content, doc_type)
        chunk = DocumentChunk(
            document_id=doc.document_id,
            document_source=doc_type,
            section_type=section_type,
            page_number=1,
            text_snippet=text_content[:500],
        )
        _add_vector_to_matter(matter_id, vec, chunk)
        doc.chunks.append(chunk)

    matter.documents.append(doc)
    logger.info(
        "Ingested text doc %s (%s): %d chunks",
        filename, doc_type.value, len(doc.chunks),
    )
    return doc


def _classify_section(text: str, doc_type: DocumentType) -> str:
    """Classify a text chunk into a section type based on keywords."""
    text_lower = text.lower() if text else ""

    if doc_type == DocumentType.ASIC_EXTRACT:
        if any(kw in text_lower for kw in ["director", "secretary", "officeholder", "officer"]):
            return "officeholders"
        if any(kw in text_lower for kw in ["share structure", "share capital", "issued capital", "class of shares"]):
            return "share_structure"
        if any(kw in text_lower for kw in ["registered office", "principal place"]):
            return "registered_office"
        if any(kw in text_lower for kw in ["ultimate holding", "holding company"]):
            return "ultimate_holding_company"
        return "general"

    elif doc_type == DocumentType.CONSTITUTION:
        if any(kw in text_lower for kw in ["objects", "powers"]):
            return "objects_and_powers"
        if any(kw in text_lower for kw in ["share class", "class of share", "preference share", "ordinary share"]):
            return "share_classes"
        if any(kw in text_lower for kw in ["voting", "vote", "poll"]):
            return "voting_rights"
        if any(kw in text_lower for kw in ["quorum"]):
            return "quorum"
        if any(kw in text_lower for kw in ["transfer", "restriction on transfer"]):
            return "share_transfer_restrictions"
        if any(kw in text_lower for kw in ["nominee", "agent", "bare trust"]):
            return "nominee_provisions"
        if any(kw in text_lower for kw in ["appointment", "removal", "director"]):
            return "director_appointment_removal"
        return "general"

    elif doc_type == DocumentType.SHAREHOLDER_REGISTER:
        if any(kw in text_lower for kw in ["shareholder", "holder", "member", "shares held"]):
            return "shareholder_entry"
        return "general"

    return "general"
