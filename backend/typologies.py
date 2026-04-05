"""
AML/CTF Tranche 2 beneficial ownership contradiction typologies.

Five hardcoded AUSTRAC/FATF typology strings embedded at startup into a FAISS
index in the same Gemini Embedding 2 vector space as document embeddings.
Contradiction contrast vectors are searched against this index to classify
the type of beneficial ownership concealment detected.
"""

import logging
from typing import Optional

import faiss
import numpy as np

from backend.embeddings import EMBEDDING_DIM, embed_texts

logger = logging.getLogger(__name__)

TYPOLOGIES = [
    {
        "id": "nominee_concealment",
        "label": "Nominee Shareholder or Director Concealment",
        "severity": "critical",
        "description": (
            "Nominee shareholder or director used to conceal ultimate beneficial "
            "owner. A nominee arrangement exists where shares are held by an agent, "
            "trustee, or corporate entity on behalf of an undisclosed principal. The "
            "nominee's presence in the shareholder register or ASIC extract is not "
            "reflected in the company constitution's nominee provisions, or the "
            "beneficial owner behind the nominee is not declared. This is a primary "
            "indicator of deliberate beneficial ownership concealment under AUSTRAC "
            "typology guidance and FATF Recommendation 24."
        ),
    },
    {
        "id": "layered_ownership",
        "label": "Complex Layered Ownership Obscuring Control",
        "severity": "high",
        "description": (
            "Complex layered ownership structures obscuring control. Multiple "
            "corporate entities are interposed between the ultimate beneficial owner "
            "and the subject company, creating opacity in the ownership chain. "
            "Intermediary companies, trusts, or partnerships are used to distance "
            "the controlling person from the registered shareholding. The effective "
            "control exercised through board appointments, voting agreements, or "
            "sole signatory authority is inconsistent with the apparent ownership "
            "percentage or governance rules in the company constitution."
        ),
    },
    {
        "id": "undisclosed_share_classes",
        "label": "Inconsistent or Undisclosed Share Classes",
        "severity": "high",
        "description": (
            "Inconsistent or undisclosed share classes between corporate documents. "
            "A share class appears in the ASIC company extract or shareholder register "
            "that is not defined in the company constitution, or the rights attached "
            "to a share class in the constitution differ materially from the rights "
            "recorded in the ASIC extract. Undisclosed or phantom share classes may "
            "carry voting rights, conversion rights, or preferential distributions "
            "that alter the effective control structure without transparent disclosure."
        ),
    },
    {
        "id": "shelf_company_transfer",
        "label": "Shelf Company Acquisition and Rapid Ownership Transfer",
        "severity": "medium",
        "description": (
            "Shelf company acquisition and rapid ownership transfer. A dormant or "
            "recently incorporated company is acquired and its ownership structure "
            "is rapidly changed, with new directors appointed and shares transferred "
            "in a short period. The company's constitution may not have been updated "
            "to reflect the new ownership structure, creating discrepancies between "
            "the ASIC register and the constitutional framework governing the entity."
        ),
    },
    {
        "id": "trust_concealment",
        "label": "Trust Structure Concealing Beneficial Ownership",
        "severity": "critical",
        "description": (
            "Trust structures used to obscure beneficial ownership. Shares or "
            "controlling interests are held through a discretionary trust, unit "
            "trust, or bare trust arrangement where the trust deed grants the "
            "appointor, guardian, or principal power to remove and replace trustees "
            "or alter beneficiary entitlements. The existence of the trust structure "
            "or the identity of the person exercising effective control through the "
            "trust is not disclosed in the beneficial ownership declaration or the "
            "company's statutory records lodged with ASIC."
        ),
    },
]

_typology_index: Optional[faiss.IndexFlatIP] = None
_typology_vectors: Optional[np.ndarray] = None
_initialized = False


async def initialize_typology_index() -> None:
    """Embed all typology descriptions and build the FAISS index. Call once at startup."""
    global _typology_index, _typology_vectors, _initialized

    logger.info("Initializing typology FAISS index with %d typologies...", len(TYPOLOGIES))

    descriptions = [t["description"] for t in TYPOLOGIES]
    vectors = await embed_texts(descriptions)

    _typology_vectors = vectors
    _typology_index = faiss.IndexFlatIP(EMBEDDING_DIM)
    _typology_index.add(vectors)
    _initialized = True

    logger.info("Typology index ready: %d vectors in %d-dim space", len(TYPOLOGIES), EMBEDDING_DIM)


def search_typologies(query_vector: np.ndarray, k: int = 3) -> list[dict]:
    """
    Search the typology index for nearest matches.

    Args:
        query_vector: L2-normalized (3072,) float32 vector.
        k: Number of results to return.

    Returns:
        List of dicts with typology fields plus similarity_score,
        sorted by descending similarity.
    """
    if not _initialized or _typology_index is None:
        raise RuntimeError("Typology index not initialized. Call initialize_typology_index() first.")

    query = query_vector.reshape(1, -1).astype(np.float32)
    scores, indices = _typology_index.search(query, min(k, len(TYPOLOGIES)))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        typology = TYPOLOGIES[idx].copy()
        typology["similarity_score"] = float(score)
        results.append(typology)

    return results


