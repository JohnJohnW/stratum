"""
Gemini-powered structured entity extraction from corporate documents.

Uses Gemini 2.0 Flash to parse ASIC extracts, constitutions, and shareholder
registers into structured Pydantic models, replacing brittle regex parsing.
"""

import asyncio
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from backend.documents import DocumentType

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "gemini-2.0-flash"


class CompanyInfo(BaseModel):
    name: str = ""
    acn: str = ""
    abn: str = ""
    registration_date: str = ""
    state: str = ""
    registered_office: str = ""


class DirectorEntry(BaseModel):
    name: str
    role: str = "Director"
    appointment_date: str = ""
    sole_signatory: bool = False
    address: str = ""


class ShareholderEntry(BaseModel):
    name: str
    quantity: int = 0
    share_class: str = "Ordinary"
    is_nominee: bool = False
    nominee_note: str = ""


class ShareClassDef(BaseModel):
    name: str
    quantity: int = 0
    voting: bool = True
    description: str = ""


class GovernanceRules(BaseModel):
    quorum_directors: int = 0
    dual_approval_threshold: str = ""
    nominee_provisions_exist: bool = False
    nominee_provisions_text: str = ""
    share_transfer_restrictions: str = ""


class OwnershipEntities(BaseModel):
    company: CompanyInfo = Field(default_factory=CompanyInfo)
    directors: list[DirectorEntry] = []
    shareholders: list[ShareholderEntry] = []
    share_classes: list[ShareClassDef] = []
    governance: GovernanceRules = Field(default_factory=GovernanceRules)
    ultimate_holding_company: str = ""


ASIC_PROMPT = """You are extracting structured data from an Australian Securities and Investments Commission (ASIC) company extract.

Extract the following information and return it as JSON:

{
  "company": {
    "name": "company name",
    "acn": "ACN number",
    "abn": "ABN number",
    "registration_date": "date registered",
    "state": "state of registration",
    "registered_office": "address"
  },
  "directors": [
    {
      "name": "full name",
      "role": "Director / Secretary / Sole Director",
      "appointment_date": "date appointed",
      "sole_signatory": true if they have sole signing authority,
      "address": "residential address"
    }
  ],
  "shareholders": [
    {
      "name": "full name or company name",
      "quantity": number of shares,
      "share_class": "Ordinary / Class B Preference / etc",
      "is_nominee": true if they appear to be holding as nominee or agent,
      "nominee_note": "any note about nominee arrangements"
    }
  ],
  "share_classes": [
    {
      "name": "class name",
      "quantity": total shares issued,
      "voting": true if voting rights exist,
      "description": "brief description of rights"
    }
  ],
  "ultimate_holding_company": "name or empty string if none"
}

Return ONLY the JSON object with no markdown formatting or explanation."""

CONSTITUTION_PROMPT = """You are extracting structured governance rules from an Australian company constitution.

Extract the following information and return it as JSON:

{
  "share_classes": [
    {
      "name": "class name",
      "quantity": authorised quantity (0 if not specified),
      "voting": true if voting rights,
      "description": "rights description"
    }
  ],
  "governance": {
    "quorum_directors": minimum directors for quorum (0 if not specified),
    "dual_approval_threshold": "dollar threshold requiring dual director approval, e.g. $50,000",
    "nominee_provisions_exist": true if the constitution addresses nominee arrangements,
    "nominee_provisions_text": "summary of nominee provisions",
    "share_transfer_restrictions": "summary of transfer restrictions"
  }
}

Return ONLY the JSON object with no markdown formatting or explanation."""

REGISTER_PROMPT = """You are extracting shareholder entries from an Australian company's Register of Members.

Extract the following information and return it as JSON:

{
  "shareholders": [
    {
      "name": "shareholder name",
      "quantity": number of shares held,
      "share_class": "share class name",
      "is_nominee": true if there is any indication this is a nominee holding,
      "nominee_note": "any note about nominee status or beneficial ownership"
    }
  ]
}

Return ONLY the JSON object with no markdown formatting or explanation."""


def _get_prompt(doc_type: DocumentType) -> str:
    prompts = {
        DocumentType.ASIC_EXTRACT: ASIC_PROMPT,
        DocumentType.CONSTITUTION: CONSTITUTION_PROMPT,
        DocumentType.SHAREHOLDER_REGISTER: REGISTER_PROMPT,
    }
    return prompts.get(doc_type, ASIC_PROMPT)


def _extract_sync(text: str, doc_type: DocumentType) -> dict:
    """Synchronous Gemini extraction call."""
    from backend.embeddings import get_client

    client = get_client()
    prompt = _get_prompt(doc_type)

    response = client.models.generate_content(
        model=EXTRACTION_MODEL,
        contents=f"{prompt}\n\nDOCUMENT TEXT:\n{text}",
    )

    raw = response.text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)

    return json.loads(raw)


async def extract_entities(text: str, doc_type: DocumentType) -> OwnershipEntities:
    """
    Extract structured ownership entities from document text using Gemini.

    Returns an OwnershipEntities model populated with whatever the document contains.
    Fields not present in the document type will remain at their defaults.
    """
    if not text or not text.strip():
        return OwnershipEntities()

    try:
        raw = await asyncio.to_thread(_extract_sync, text, doc_type)
    except Exception as e:
        logger.error("Gemini extraction failed for %s: %s", doc_type.value, e)
        return OwnershipEntities()

    # Build OwnershipEntities from the partial JSON response
    entities = OwnershipEntities()

    if "company" in raw:
        entities.company = CompanyInfo(**raw["company"])

    if "directors" in raw:
        entities.directors = [DirectorEntry(**d) for d in raw["directors"]]

    if "shareholders" in raw:
        entities.shareholders = [ShareholderEntry(**s) for s in raw["shareholders"]]

    if "share_classes" in raw:
        entities.share_classes = [ShareClassDef(**sc) for sc in raw["share_classes"]]

    if "governance" in raw:
        entities.governance = GovernanceRules(**raw["governance"])

    if "ultimate_holding_company" in raw:
        entities.ultimate_holding_company = raw["ultimate_holding_company"]

    logger.info(
        "Extracted from %s: %d directors, %d shareholders, %d share classes",
        doc_type.value,
        len(entities.directors),
        len(entities.shareholders),
        len(entities.share_classes),
    )
    return entities
