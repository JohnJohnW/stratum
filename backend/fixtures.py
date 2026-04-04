"""
Demo fixture data for Fixture Holdings Pty Ltd.

Fixture A: All three documents are consistent, zero contradictions.
Fixture B: Three deliberate inconsistencies that trigger contradiction flags.

All entities are fictional. Names and addresses are synthetic.
"""

from backend.documents import DocumentType

ENTITY_INFO = {
    "entity_name": "Fixture Holdings Pty Ltd",
    "acn": "000 000 001",
}

# ---------------------------------------------------------------------------
# FIXTURE A: CLEAN (no contradictions)
# ---------------------------------------------------------------------------

FIXTURE_A_ASIC_EXTRACT = """AUSTRALIAN SECURITIES AND INVESTMENTS COMMISSION
COMPANY EXTRACT

Company Name: Fixture Holdings Pty Ltd
ACN: 000 000 001
ABN: 51 000 000 001
Type: Australian Proprietary Company, Limited By Shares
Status: Registered
Registration Date: 01/07/2020
State of Registration: New South Wales
Registered Office: Level 12, 88 Pitt Street, Sydney NSW 2000
Principal Place of Business: Level 12, 88 Pitt Street, Sydney NSW 2000

OFFICEHOLDERS
James Mitchell - Director, appointed 01/07/2020
  Address: 27 Harbour View Drive, Mosman NSW 2088
Sarah Blackwood - Director and Secretary, appointed 01/07/2020
  Address: 14 Acacia Lane, Toorak VIC 3142

SHARE STRUCTURE
Total Issued Capital:
  1,000 Ordinary Shares, fully paid, voting rights of one vote per share
  500 Class B Preference Shares, fully paid, non-voting, fixed 8% cumulative dividend

SHAREHOLDERS
James Mitchell - 400 Ordinary Shares
Pacific Trust Services Pty Ltd (ACN 000 000 002) - 600 Ordinary Shares
Sarah Blackwood - 500 Class B Preference Shares

ULTIMATE HOLDING COMPANY
None recorded.

This extract was produced by the Australian Securities and Investments Commission.
"""

FIXTURE_A_CONSTITUTION = """CONSTITUTION OF FIXTURE HOLDINGS PTY LTD
ACN 000 000 001
Adopted by Special Resolution on 01 July 2020

1. OBJECTS AND POWERS
The Company is established for the purpose of property development, investment,
and such other lawful activities as the directors may determine from time to time.
The Company has the legal capacity and powers of an individual under section 124
of the Corporations Act 2001 (Cth).

2. SHARE CLASSES
2.1 Ordinary Shares
The Company may issue Ordinary Shares conferring on each holder one vote per share
at general meetings, the right to participate in dividends declared by the directors,
and the right to participate in surplus assets on winding up in proportion to the
number of shares held.

2.2 Class B Preference Shares
The Company may issue Class B Preference Shares conferring on each holder a fixed
cumulative preferential dividend of 8% per annum on the paid-up capital of each
share. Class B Preference Shares carry no voting rights at general meetings except
on a resolution to wind up the Company or to vary the rights attached to the class.
Class B Preference Shares rank in priority to Ordinary Shares on a return of capital
on winding up.

3. NOMINEE PROVISIONS
3.1 The Company does not recognise any nominee, trustee, or agency arrangement
in respect of shares unless such arrangement is disclosed in writing to the
Company Secretary and recorded in the Register of Members.
3.2 Where shares are held by a corporate entity, the directors may require
disclosure of the ultimate beneficial owner of those shares.

4. QUORUM AND DECISION MAKING
4.1 A quorum for a meeting of directors is two directors present in person or
by electronic communication.
4.2 Resolutions of the directors are passed by a simple majority of votes of
directors present and entitled to vote.
4.3 For any transaction, contract, or commitment with a value exceeding $50,000,
the approval of at least two directors is required.

5. DIRECTOR APPOINTMENT AND REMOVAL
5.1 Directors are appointed by ordinary resolution of the members.
5.2 A director may be removed by ordinary resolution of the members in accordance
with section 203D of the Corporations Act 2001 (Cth).

6. SHARE TRANSFER RESTRICTIONS
6.1 No share may be transferred without the prior approval of the directors.
6.2 The directors may refuse to register a transfer of shares without giving
any reason for the refusal.
"""

FIXTURE_A_REGISTER = """REGISTER OF MEMBERS
FIXTURE HOLDINGS PTY LTD (ACN 000 000 001)
As at 01 July 2020

SHAREHOLDER REGISTER

| Name                              | Share Class          | Quantity | Certificate | Date Allotted |
|-----------------------------------|----------------------|----------|-------------|---------------|
| James Mitchell                    | Ordinary Shares      | 400      | CERT-001    | 01/07/2020    |
| Pacific Trust Services Pty Ltd    | Ordinary Shares      | 600      | CERT-002    | 01/07/2020    |
| Sarah Blackwood                   | Class B Preference   | 500      | CERT-003    | 01/07/2020    |

TOTAL ORDINARY SHARES ISSUED: 1,000
TOTAL CLASS B PREFERENCE SHARES ISSUED: 500

Registered Office: Level 12, 88 Pitt Street, Sydney NSW 2000

This Register of Members has been maintained in accordance with
section 169 of the Corporations Act 2001 (Cth).

Certified by: Sarah Blackwood, Company Secretary
Date: 01 July 2020
"""

# ---------------------------------------------------------------------------
# FIXTURE B: DIRTY (3 deliberate contradictions)
# ---------------------------------------------------------------------------

# Contradiction 1: ASIC extract is the same, but the REGISTER adds Pacific Trust
# Services as a nominee-like entity. The CONSTITUTION in fixture B does NOT have
# nominee provisions acknowledging this arrangement. The constitution omits
# Section 3 (Nominee Provisions) entirely.

FIXTURE_B_ASIC_EXTRACT = """AUSTRALIAN SECURITIES AND INVESTMENTS COMMISSION
COMPANY EXTRACT

Company Name: Fixture Holdings Pty Ltd
ACN: 000 000 001
ABN: 51 000 000 001
Type: Australian Proprietary Company, Limited By Shares
Status: Registered
Registration Date: 01/07/2020
State of Registration: New South Wales
Registered Office: Level 12, 88 Pitt Street, Sydney NSW 2000
Principal Place of Business: Level 12, 88 Pitt Street, Sydney NSW 2000

OFFICEHOLDERS
James Mitchell - Sole Director, appointed 01/07/2020
  Sole signatory authority, unlimited transaction authority
  Address: 27 Harbour View Drive, Mosman NSW 2088
Sarah Blackwood - Secretary, appointed 01/07/2020
  Address: 14 Acacia Lane, Toorak VIC 3142

SHARE STRUCTURE
Total Issued Capital:
  1,000 Ordinary Shares, fully paid, voting rights of one vote per share
  500 Class B Preference Shares, fully paid, non-voting, fixed 8% cumulative dividend
  200 Class C Convertible Preference Shares, fully paid, convertible to Ordinary at 1:1 ratio

SHAREHOLDERS
James Mitchell - 400 Ordinary Shares
Pacific Trust Services Pty Ltd (ACN 000 000 002) - 600 Ordinary Shares
Sarah Blackwood - 500 Class B Preference Shares
James Mitchell - 200 Class C Convertible Preference Shares

ULTIMATE HOLDING COMPANY
None recorded.

This extract was produced by the Australian Securities and Investments Commission.
"""

# Contradiction 2: Constitution does NOT define Class C Convertible Preference Shares,
# but the ASIC extract above lists them.
# Contradiction 3: Constitution requires two-director quorum for transactions >$50k,
# but the ASIC extract lists James Mitchell as Sole Director with sole signatory authority.

FIXTURE_B_CONSTITUTION = """CONSTITUTION OF FIXTURE HOLDINGS PTY LTD
ACN 000 000 001
Adopted by Special Resolution on 01 July 2020

1. OBJECTS AND POWERS
The Company is established for the purpose of property development, investment,
and such other lawful activities as the directors may determine from time to time.
The Company has the legal capacity and powers of an individual under section 124
of the Corporations Act 2001 (Cth).

2. SHARE CLASSES
2.1 Ordinary Shares
The Company may issue Ordinary Shares conferring on each holder one vote per share
at general meetings, the right to participate in dividends declared by the directors,
and the right to participate in surplus assets on winding up in proportion to the
number of shares held. The total authorised Ordinary Shares is 1,000.

2.2 Class B Preference Shares
The Company may issue Class B Preference Shares conferring on each holder a fixed
cumulative preferential dividend of 8% per annum on the paid-up capital of each
share. Class B Preference Shares carry no voting rights at general meetings except
on a resolution to wind up the Company or to vary the rights attached to the class.
The total authorised Class B Preference Shares is 500.

2.3 No other class of shares is authorised under this Constitution. The creation
of any new class of shares requires a special resolution of the members and an
amendment to this Constitution under section 136 of the Corporations Act 2001 (Cth).

3. QUORUM AND DECISION MAKING
3.1 A quorum for a meeting of directors is two directors present in person or
by electronic communication.
3.2 Resolutions of the directors are passed by a simple majority of votes of
directors present and entitled to vote.
3.3 For any transaction, contract, or commitment with a value exceeding $50,000,
the approval of at least two directors is required. No single director may
unilaterally authorise expenditure or enter into binding commitments above this
threshold on behalf of the Company.

4. DIRECTOR APPOINTMENT AND REMOVAL
4.1 The Company shall have a minimum of two directors at all times.
4.2 Directors are appointed by ordinary resolution of the members.
4.3 A director may be removed by ordinary resolution of the members in accordance
with section 203D of the Corporations Act 2001 (Cth).

5. SHARE TRANSFER RESTRICTIONS
5.1 No share may be transferred without the prior approval of the directors.
5.2 The directors may refuse to register a transfer of shares without giving
any reason for the refusal.
"""

FIXTURE_B_REGISTER = """REGISTER OF MEMBERS
FIXTURE HOLDINGS PTY LTD (ACN 000 000 001)
As at 01 July 2020

SHAREHOLDER REGISTER

| Name                              | Share Class                    | Quantity | Certificate | Date Allotted |
|-----------------------------------|--------------------------------|----------|-------------|---------------|
| James Mitchell                    | Ordinary Shares                | 400      | CERT-001    | 01/07/2020    |
| Pacific Trust Services Pty Ltd    | Ordinary Shares                | 600      | CERT-002    | 01/07/2020    |
| Sarah Blackwood                   | Class B Preference Shares      | 500      | CERT-003    | 01/07/2020    |
| James Mitchell                    | Class C Convertible Preference | 200      | CERT-004    | 15/09/2020    |

Note: Pacific Trust Services Pty Ltd holds shares as nominee for an undisclosed
beneficial owner. No nominee arrangement documentation has been provided to the
Company Secretary as at the date of this register.

TOTAL ORDINARY SHARES ISSUED: 1,000
TOTAL CLASS B PREFERENCE SHARES ISSUED: 500
TOTAL CLASS C CONVERTIBLE PREFERENCE SHARES ISSUED: 200

Registered Office: Level 12, 88 Pitt Street, Sydney NSW 2000

This Register of Members has been maintained in accordance with
section 169 of the Corporations Act 2001 (Cth).

Certified by: Sarah Blackwood, Company Secretary
Date: 15 September 2020
"""


# ---------------------------------------------------------------------------
# Targeted claim sentences for embedding (short, semantically focused).
# These maximise semantic contrast between contradicting pairs while the
# full document text (raw_text) is preserved for display in the UI.
# ---------------------------------------------------------------------------

# Fixture A: consistent claims
_A_ASIC_OFFICEHOLDERS_CLAIM = (
    "James Mitchell and Sarah Blackwood are both appointed directors with joint authority. "
    "Both directors participate equally in governance. All decisions are made jointly by the two directors."
)
_A_ASIC_SHARES_CLAIM = (
    "The company has issued exactly two classes of shares: 1,000 Ordinary Shares and "
    "500 Class B Preference Shares. No other share classes exist in the capital structure."
)
_A_ASIC_SHAREHOLDERS_CLAIM = (
    "James Mitchell holds 400 Ordinary Shares as beneficial owner. "
    "Pacific Trust Services Pty Ltd holds 600 Ordinary Shares and has disclosed its nominee arrangement "
    "in writing to the Company Secretary as recorded in the Register. "
    "Sarah Blackwood holds 500 Class B Preference Shares as beneficial owner."
)
_A_CONST_SHARE_CLASSES_CLAIM = (
    "The company is authorised to issue Ordinary Shares and Class B Preference Shares, two classes only. "
    "These are the only authorised share classes under this Constitution."
)
_A_CONST_NOMINEE_CLAIM = (
    "Nominee and bare trust shareholding arrangements are permitted provided they are disclosed "
    "in writing to the Company Secretary and recorded in the Register of Members. "
    "Pacific Trust Services Pty Ltd's nominee arrangement has been properly disclosed and recorded."
)
_A_CONST_QUORUM_CLAIM = (
    "A quorum for director meetings requires two directors present. "
    "Both directors must jointly approve transactions above $50,000. "
    "The two-director structure ensures shared governance responsibility."
)
_A_REGISTER_CLAIM = (
    "Shareholders: James Mitchell, 400 Ordinary Shares (beneficial owner). "
    "Pacific Trust Services Pty Ltd, 600 Ordinary Shares (nominee, disclosure lodged with Company Secretary). "
    "Sarah Blackwood, 500 Class B Preference Shares (beneficial owner)."
)

# Fixture B: contradicting claims
_B_ASIC_OFFICEHOLDERS_CLAIM = (
    "James Mitchell is the sole director. He holds sole and exclusive signing authority without restriction. "
    "A single director exercises complete unilateral authority to execute any contract of any value. "
    "No co-signature or second director approval is required for any transaction."
)
_B_ASIC_SHARES_CLAIM = (
    "The company has issued three classes of shares: Ordinary Shares, Class B Preference Shares, "
    "and Class C Convertible Preference Shares. Class C Convertible Preference Shares are a distinct "
    "third class convertible to Ordinary Shares at a 1:1 ratio, recorded in the capital structure."
)
_B_ASIC_SHAREHOLDERS_CLAIM = (
    "James Mitchell holds 400 Ordinary Shares. "
    "Pacific Trust Services Pty Ltd holds 600 Ordinary Shares. "
    "Sarah Blackwood holds 500 Class B Preference Shares. "
    "James Mitchell holds 200 Class C Convertible Preference Shares."
)
_B_CONST_SHARE_CLASSES_CLAIM = (
    "Only two share classes are authorised: Ordinary Shares and Class B Preference Shares. "
    "No other class of shares has been created or authorised under this Constitution. "
    "Class C Convertible Preference Shares do not exist and are not authorised. "
    "Creating any new class requires a special resolution to amend this Constitution."
)
_B_CONST_QUORUM_CLAIM = (
    "It is expressly prohibited for a single director to bind the company alone. "
    "A mandatory minimum of two directors must be present and approve all board decisions. "
    "No single director possesses unilateral authority of any kind. "
    "All transactions above $50,000 require dual director co-authorization. This requirement cannot be waived."
)
_B_CONST_NO_NOMINEES_CLAIM = (
    "This company has no nominee shareholding arrangements of any kind. "
    "All shareholders are the absolute and direct beneficial owner of their registered shares. "
    "Nominee, bare trust, and undisclosed beneficial owner arrangements do not exist and are prohibited. "
    "The shareholder register accurately and completely reflects the true beneficial ownership of all shares."
)
_B_REGISTER_CLAIM = (
    "Pacific Trust Services Pty Ltd holds 600 Ordinary Shares as nominee for an undisclosed beneficial owner. "
    "The identity of the true beneficial owner behind this nominee arrangement has NOT been disclosed "
    "to the Company Secretary. No nominee arrangement documentation has been provided or recorded."
)


def get_fixture_a() -> tuple[dict, list[tuple[str, DocumentType, str, list[tuple[str, str]]]]]:
    """
    Returns (entity_info, documents) for Fixture A (clean).

    Each document is (filename, doc_type, full_text, sections) where sections
    is a list of (section_type, embed_text) tuples. The embed_text is a focused
    claim sentence that captures the semantic content of each section for
    embedding; the full document text is stored in raw_text for UI display.
    """
    return ENTITY_INFO, [
        (
            "ASIC_Extract_FixtureHoldings.pdf",
            DocumentType.ASIC_EXTRACT,
            FIXTURE_A_ASIC_EXTRACT,
            [
                ("officeholders", _A_ASIC_OFFICEHOLDERS_CLAIM),
                ("share_structure", _A_ASIC_SHARES_CLAIM),
                ("general", _A_ASIC_SHAREHOLDERS_CLAIM),
            ],
        ),
        (
            "Constitution_FixtureHoldings.pdf",
            DocumentType.CONSTITUTION,
            FIXTURE_A_CONSTITUTION,
            [
                ("share_classes", _A_CONST_SHARE_CLASSES_CLAIM),
                ("nominee_provisions", _A_CONST_NOMINEE_CLAIM),
                ("quorum", _A_CONST_QUORUM_CLAIM),
            ],
        ),
        (
            "ShareRegister_FixtureHoldings.pdf",
            DocumentType.SHAREHOLDER_REGISTER,
            FIXTURE_A_REGISTER,
            [
                ("shareholder_entry", _A_REGISTER_CLAIM),
            ],
        ),
    ]


def get_fixture_b() -> tuple[dict, list[tuple[str, DocumentType, str, list[tuple[str, str]]]]]:
    """
    Returns (entity_info, documents) for Fixture B (3 contradictions).

    Contradictions (each detected via cosine similarity below threshold):
    1. ASIC officeholders (sole director, unlimited authority) vs
       Constitution quorum (two directors mandatory, sole action prohibited)
       Typology: layered_ownership / nominee_concealment
    2. ASIC share_structure (three classes including Class C) vs
       Constitution share_classes (only two classes authorised, no Class C)
       Typology: undisclosed_share_classes
    3. Register shareholder_entry (Pacific Trust as nominee, undisclosed BO) vs
       Constitution nominee_provisions denial (no nominees exist, all are beneficial owners)
       Typology: nominee_concealment / trust_concealment
    """
    return ENTITY_INFO, [
        (
            "ASIC_Extract_FixtureHoldings.pdf",
            DocumentType.ASIC_EXTRACT,
            FIXTURE_B_ASIC_EXTRACT,
            [
                ("officeholders", _B_ASIC_OFFICEHOLDERS_CLAIM),
                ("share_structure", _B_ASIC_SHARES_CLAIM),
                ("general", _B_ASIC_SHAREHOLDERS_CLAIM),
            ],
        ),
        (
            "Constitution_FixtureHoldings.pdf",
            DocumentType.CONSTITUTION,
            FIXTURE_B_CONSTITUTION,
            [
                ("share_classes", _B_CONST_SHARE_CLASSES_CLAIM),
                ("quorum", _B_CONST_QUORUM_CLAIM),
                # No nominee provisions in Fixture B constitution, replaced by explicit denial
                ("nominee_provisions", _B_CONST_NO_NOMINEES_CLAIM),
            ],
        ),
        (
            "ShareRegister_FixtureHoldings.pdf",
            DocumentType.SHAREHOLDER_REGISTER,
            FIXTURE_B_REGISTER,
            [
                ("shareholder_entry", _B_REGISTER_CLAIM),
            ],
        ),
    ]


def _extract_section(text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between two markers."""
    start = text.find(start_marker)
    if start == -1:
        return text
    end = text.find(end_marker, start + len(start_marker))
    if end == -1:
        return text[start:]
    return text[start:end].strip()
