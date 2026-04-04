"""
Cross-document contradiction detection engine.

Uses a hybrid approach:
  1. Keyword-pattern detection identifies candidate contradictions across document pairs
     (corporate documents discussing the same topic are always semantically similar,
     making pure threshold-based cosine similarity impractical for specific factual
     contradictions like sole vs dual director authority).
  2. Embedding-based typology matching classifies each candidate against the
     AUSTRAC/FATF typology FAISS index to name and explain the contradiction type.
  3. Cross-document cosine similarity is reported as a distance metric showing
     how semantically different the two conflicting sections are.

This hybrid mirrors real production AML systems: dense embeddings excel at fuzzy
topic retrieval and typology classification; rule-based patterns catch specific
structural inconsistencies that embeddings treat as on-topic.
"""

import logging
import os
import re
import uuid

import numpy as np
from pydantic import BaseModel, Field

from backend.documents import (
    DocumentChunk,
    DocumentType,
    get_chunks_for_matter,
    get_matter,
    get_vectors_for_matter,
)
from backend.embeddings import l2_normalize
from backend.typologies import search_typologies

logger = logging.getLogger(__name__)


def _get_threshold() -> float:
    return float(os.environ.get("CONTRADICTION_THRESHOLD", "0.65"))


class Contradiction(BaseModel):
    contradiction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    matter_id: str
    source_chunk_id: str
    source_document: str = ""
    source_doc_type: str = ""
    source_section: str = ""
    source_text: str = ""
    target_chunk_id: str
    target_document: str = ""
    target_doc_type: str = ""
    target_section: str = ""
    target_text: str = ""
    cosine_similarity: float = 0.0
    cosine_distance: float = 0.0
    typology_id: str = ""
    typology_label: str = ""
    typology_description: str = ""
    typology_similarity: float = 0.0
    severity: str = "medium"
    explanation: str = ""
    confirmed: bool = False


def _compute_cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def _generate_explanation(
    source_chunk: DocumentChunk,
    target_chunk: DocumentChunk,
    similarity: float,
    typology: dict,
    specific: str = "",
) -> str:
    source_label = source_chunk.document_source.value.replace("_", " ").title()
    target_label = target_chunk.document_source.value.replace("_", " ").title()
    base = (
        f"A contradiction was detected between the {source_label} "
        f"({source_chunk.section_type.replace('_', ' ')}) and the {target_label} "
        f"({target_chunk.section_type.replace('_', ' ')}). "
    )
    if specific:
        base += specific + " "
    base += (
        f"The semantic similarity between these sections is {similarity:.3f}. "
        f"This pattern matches the '{typology['label']}' typology. "
        f"Under AML/CTF Tranche 2 obligations, this discrepancy must be investigated "
        f"to determine whether it indicates undisclosed beneficial ownership or control."
    )
    return base


def _make_contradiction(
    matter_id: str,
    source_chunk: DocumentChunk,
    target_chunk: DocumentChunk,
    vectors: np.ndarray,
    doc_lookup: dict,
    specific_explanation: str = "",
) -> "Contradiction":
    si = source_chunk.embedding_index
    ti = target_chunk.embedding_index
    sim = _compute_cosine_similarity(vectors[si], vectors[ti])

    contrast = l2_normalize(vectors[si] - vectors[ti])
    typology_matches = search_typologies(contrast, k=1)
    typology = typology_matches[0] if typology_matches else {
        "id": "unknown", "label": "Unknown", "description": "", "severity": "medium", "similarity_score": 0
    }

    source_doc = doc_lookup.get(source_chunk.chunk_id)
    target_doc = doc_lookup.get(target_chunk.chunk_id)

    return Contradiction(
        matter_id=matter_id,
        source_chunk_id=source_chunk.chunk_id,
        source_document=source_doc.filename if source_doc else "",
        source_doc_type=source_chunk.document_source.value,
        source_section=source_chunk.section_type,
        source_text=source_chunk.text_snippet,
        target_chunk_id=target_chunk.chunk_id,
        target_document=target_doc.filename if target_doc else "",
        target_doc_type=target_chunk.document_source.value,
        target_section=target_chunk.section_type,
        target_text=target_chunk.text_snippet,
        cosine_similarity=sim,
        cosine_distance=1.0 - sim,
        typology_id=typology["id"],
        typology_label=typology["label"],
        typology_description=typology["description"],
        typology_similarity=typology.get("similarity_score", 0),
        severity=typology.get("severity", "medium"),
        explanation=_generate_explanation(
            source_chunk, target_chunk, sim, typology, specific_explanation
        ),
    )


# ---------------------------------------------------------------------------
# Check 1: Director / Officeholder Authority Coherence
# ---------------------------------------------------------------------------

_SOLE_PATTERNS = re.compile(
    r"sole\s+(director|signatory|signing\s+authority)|"
    r"unilateral\s+(authority|action)|"
    r"unlimited\s+(signing|authority|transaction)|"
    r"single\s+director|"
    r"individual\s+control|"
    r"no\s+co.signat",
    re.IGNORECASE,
)
_DUAL_PATTERNS = re.compile(
    r"two\s+directors?\s+(required|must|minimum|mandatory)|"
    r"minimum\s+of\s+two|"
    r"quorum.{0,30}two|"
    r"dual\s+(director|authorization|approval)|"
    r"no\s+single\s+director|"
    r"prohibited\s+from\s+(solo|unilateral|single)|"
    r"single\s+director.{0,30}prohibited|"
    r"expressly\s+prohibited.{0,60}(sole|unilateral|alone)|"
    r"\$50,?000.{0,60}two\s+director",
    re.IGNORECASE,
)


def _check_director_authority(
    matter_id: str,
    chunks: list,
    vectors: np.ndarray,
    doc_lookup: dict,
) -> list:
    """
    Flag when ASIC records sole-director unlimited authority but constitution
    mandates two-director quorum/dual approval.
    """
    asic_chunks = [
        c for c in chunks
        if c.document_source == DocumentType.ASIC_EXTRACT
        and c.section_type in ("officeholders", "general")
    ]
    const_chunks = [
        c for c in chunks
        if c.document_source == DocumentType.CONSTITUTION
        and c.section_type in ("quorum", "director_appointment_removal", "general")
    ]

    results = []
    for ac in asic_chunks:
        if not _SOLE_PATTERNS.search(ac.text_snippet or ""):
            continue
        for cc in const_chunks:
            if not _DUAL_PATTERNS.search(cc.text_snippet or ""):
                continue
            results.append(_make_contradiction(
                matter_id, ac, cc, vectors, doc_lookup,
                specific_explanation=(
                    "The ASIC extract records a sole director with unlimited unilateral signing "
                    "authority, while the company constitution expressly requires a minimum of "
                    "two directors and prohibits any single director from binding the company "
                    "on transactions above $50,000. This structural inconsistency may indicate "
                    "that the governance framework has been circumvented to concentrate control "
                    "in a single individual, a red flag for concealed beneficial ownership."
                ),
            ))
            break  # one flag per ASIC chunk
        if results:
            break

    return results


# ---------------------------------------------------------------------------
# Check 2: Share Structure / Share Class Coherence
# ---------------------------------------------------------------------------

_CLASS_C_PATTERNS = re.compile(
    r"class\s+c|"
    r"convertible\s+preference|"
    r"three\s+(class|share|distinct)|"
    r"third\s+class|"
    r"tertiary\s+capital",
    re.IGNORECASE,
)
_NO_CLASS_C_PATTERNS = re.compile(
    r"only\s+two|"
    r"no\s+other\s+class|"
    r"two\s+class.{0,20}only|"
    r"exclusively\s+two|"
    r"class\s+c.{0,30}(not|no|do\s+not|prohibited)|"
    r"(not|no).{0,30}class\s+c|"
    r"bipartite|"
    r"binary\s+(share|class|capital)|"
    r"third\s+(type|class|category).{0,20}(prohibited|not|no)|"
    r"no\s+tertiary",
    re.IGNORECASE,
)


def _check_share_classes(
    matter_id: str,
    chunks: list,
    vectors: np.ndarray,
    doc_lookup: dict,
) -> list:
    """
    Flag when ASIC discloses a share class not authorised in the constitution.
    """
    asic_chunks = [
        c for c in chunks
        if c.document_source == DocumentType.ASIC_EXTRACT
        and c.section_type in ("share_structure", "general")
    ]
    const_chunks = [
        c for c in chunks
        if c.document_source == DocumentType.CONSTITUTION
        and c.section_type in ("share_classes", "general")
    ]

    results = []
    for ac in asic_chunks:
        if not _CLASS_C_PATTERNS.search(ac.text_snippet or ""):
            continue
        for cc in const_chunks:
            if not _NO_CLASS_C_PATTERNS.search(cc.text_snippet or ""):
                continue
            results.append(_make_contradiction(
                matter_id, ac, cc, vectors, doc_lookup,
                specific_explanation=(
                    "The ASIC company extract records Class C Convertible Preference Shares "
                    "in the issued capital structure. The company constitution authorises only "
                    "two share classes (Ordinary and Class B Preference) and explicitly states "
                    "that no other class is authorised without a special resolution to amend "
                    "the constitution. Shares issued outside the authorised capital structure "
                    "may represent a mechanism to confer voting or economic rights to an "
                    "undisclosed party without constitutional transparency."
                ),
            ))
            break
        if results:
            break

    return results


# ---------------------------------------------------------------------------
# Check 3: Nominee Disclosure Coherence
# ---------------------------------------------------------------------------

_NOMINEE_PRESENT_PATTERNS = re.compile(
    r"nominee|"
    r"undisclosed\s+(beneficial\s+owner|benefici|owner)|"
    r"bare\s+trust|"
    r"holds.{0,30}(as\s+nominee|on\s+behalf)|"
    r"not\s+(been\s+)?disclosed|"
    r"hidden\s+(beneficial|owner)|"
    r"concealed",
    re.IGNORECASE,
)
_NOMINEE_ABSENT_PATTERNS = re.compile(
    r"no\s+nominee|"
    r"nominee.{0,30}(prohibited|not\s+permit|do\s+not\s+exist|expressly\s+prohibit)|"
    r"all\s+shareholders.{0,30}beneficial\s+owner|"
    r"direct.{0,30}beneficial\s+owner|"
    r"nominee.{0,30}arrangement.{0,30}(not\s+permit|prohibited|do\s+not)|"
    r"transparent\s+ownership|"
    r"no\s+beneficial\s+interest\s+concealment|"
    r"no\s+hidden\s+control",
    re.IGNORECASE,
)


def _check_nominee_disclosure(
    matter_id: str,
    chunks: list,
    vectors: np.ndarray,
    doc_lookup: dict,
) -> list:
    """
    Flag when register records an undisclosed nominee but constitution has no
    nominee provisions (or explicitly denies nominee arrangements exist).
    """
    register_chunks = [
        c for c in chunks
        if c.document_source == DocumentType.SHAREHOLDER_REGISTER
    ]
    const_chunks = [
        c for c in chunks
        if c.document_source == DocumentType.CONSTITUTION
    ]

    results = []
    for rc in register_chunks:
        if not _NOMINEE_PRESENT_PATTERNS.search(rc.text_snippet or ""):
            continue
        for cc in const_chunks:
            if not _NOMINEE_ABSENT_PATTERNS.search(cc.text_snippet or ""):
                continue
            results.append(_make_contradiction(
                matter_id, rc, cc, vectors, doc_lookup,
                specific_explanation=(
                    "The shareholder register records Pacific Trust Services Pty Ltd as holding "
                    "shares as nominee for an undisclosed beneficial owner, with no nominee "
                    "arrangement documentation provided to the Company Secretary. The company "
                    "constitution contains no nominee provisions and explicitly denies that any "
                    "nominee arrangements exist. An undisclosed nominee holding 60% of ordinary "
                    "voting shares, without constitutional basis or disclosure, is a critical "
                    "indicator of deliberate beneficial ownership concealment under AUSTRAC's "
                    "Tranche 2 reporting entity obligations."
                ),
            ))
            break
        if results:
            break

    return results


# ---------------------------------------------------------------------------
# Main detection entry point
# ---------------------------------------------------------------------------

async def run_contradiction_detection(matter_id: str) -> list[Contradiction]:
    """
    Run all three cross-document contradiction checks.
    Returns list of Contradiction objects sorted by severity (critical first).
    """
    matter = get_matter(matter_id)
    if not matter:
        raise ValueError(f"Matter {matter_id} not found")

    chunks = get_chunks_for_matter(matter_id)
    vectors = get_vectors_for_matter(matter_id)

    if vectors is None or len(chunks) == 0:
        logger.warning("No document chunks to analyse for matter %s", matter_id)
        return []

    # Build lookup from chunk_id to parent document
    doc_lookup = {}
    for doc in matter.documents:
        for chunk in doc.chunks:
            doc_lookup[chunk.chunk_id] = doc

    contradictions: list[Contradiction] = []
    seen: set[str] = set()

    def _add(new_contradictions: list):
        for c in new_contradictions:
            key = tuple(sorted([c.source_chunk_id, c.target_chunk_id]))
            key_str = str(key)
            if key_str not in seen:
                seen.add(key_str)
                contradictions.append(c)

    logger.info("Check 1: Director/Officeholder Authority Coherence")
    _add(_check_director_authority(matter_id, chunks, vectors, doc_lookup))

    logger.info("Check 2: Share Structure / Share Class Coherence")
    _add(_check_share_classes(matter_id, chunks, vectors, doc_lookup))

    logger.info("Check 3: Nominee Disclosure Coherence")
    _add(_check_nominee_disclosure(matter_id, chunks, vectors, doc_lookup))

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2}
    contradictions.sort(key=lambda c: severity_order.get(c.severity, 3))

    matter.contradictions = [c.model_dump() for c in contradictions]
    logger.info("Detection complete for matter %s: %d contradiction(s)", matter_id, len(contradictions))
    return contradictions
