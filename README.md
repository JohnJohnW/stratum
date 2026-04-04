# STRATUM

Beneficial ownership contradiction detection for Australian law firm AML/CTF Tranche 2 compliance (effective July 2026).

STRATUM accepts three corporate documents for a client matter (ASIC company extract, company constitution, shareholder register), embeds all three using Gemini Embedding 2 into a single shared 3072-dimensional vector space, detects semantic contradictions across documents that indicate undisclosed beneficial ownership, and renders a live ownership graph with contradiction flags and matched AUSTRAC/FATF typologies.

## Quick Start

### Prerequisites

- Python 3.11+
- [Poppler](https://poppler.freedesktop.org/) for PDF rendering (`brew install poppler` on macOS)
- [Gemini API key](https://aistudio.google.com/apikey)

### Setup

```bash
git clone https://github.com/JohnJohnW/stratum.git
cd stratum
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
# Add your GEMINI_API_KEY to .env

uvicorn backend.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) and click **Fixture B** to see three contradiction flags detected across the demo entity.

## Architecture

### System Overview

```mermaid
graph LR
    subgraph Documents
        A[ASIC Extract]
        B[Constitution]
        C[Share Register]
    end

    subgraph Embedding
        D[Gemini Embedding 2]
    end

    subgraph Detection
        E[FAISS Index]
        F[Pattern Matching]
        G[Typology Classifier]
    end

    subgraph Output
        H[Ownership Graph]
        I[CDD Report]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    G --> I
```

### Contradiction Detection Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant EMB as Gemini Embedding 2
    participant IDX as FAISS Index
    participant DET as Detection Engine
    participant TYP as Typology Index

    U->>API: Upload 3 documents
    API->>EMB: Embed each page/section
    EMB-->>IDX: Store 3072-dim vectors

    U->>API: Run detection
    API->>DET: Cross-document checks
    DET->>IDX: Retrieve section vectors
    DET->>DET: Compute cosine similarity
    DET->>TYP: Classify via contrast vector
    TYP-->>DET: Matched typology
    DET-->>API: Contradiction results
    API-->>U: Graph + flags via WebSocket
```

### Ownership Graph Structure (Fixture B)

```mermaid
graph BT
    JM_DIR["James Mitchell<br/>Director"]
    SB_DIR["Sarah Blackwood<br/>Director + Secretary"]
    JM_SH["James Mitchell<br/>400 Ordinary"]
    PT_SH["Pacific Trust Services<br/>600 Ordinary"]
    SB_SH["Sarah Blackwood<br/>500 Class B Pref"]
    CO["Fixture Holdings Pty Ltd<br/>ACN 000 000 001"]
    ORD["Ordinary Shares<br/>1,000 issued"]
    PREF["Class B Preference<br/>500 issued"]
    CC["Class C Convertible<br/>Not in Constitution"]

    JM_DIR -->|Controls| CO
    SB_DIR -->|Controls| CO
    JM_SH -->|40% Ordinary| CO
    PT_SH -->|60% Ordinary| CO
    SB_SH -->|100% Class B| CO
    ORD -->|Issued Under| CO
    PREF -->|Issued Under| CO
    CC -.->|Undisclosed| CO
    PT_SH -.->|Nominee?| CO
```

### Data Model

```mermaid
erDiagram
    MATTER ||--o{ DOCUMENT : contains
    MATTER ||--o{ CONTRADICTION : has
    DOCUMENT ||--o{ CHUNK : "split into"
    CONTRADICTION }o--|| CHUNK : "source"
    CONTRADICTION }o--|| CHUNK : "target"
    CONTRADICTION }o--|| TYPOLOGY : "matches"

    MATTER {
        string matter_id PK
        string entity_name
        string acn
    }

    DOCUMENT {
        string document_id PK
        string matter_id FK
        string filename
        string doc_type
        string sha256_hash
    }

    CHUNK {
        string chunk_id PK
        string document_id FK
        string section_type
        int page_number
        string text_snippet
        int embedding_index
    }

    CONTRADICTION {
        string contradiction_id PK
        string matter_id FK
        float cosine_similarity
        string typology_id FK
        string severity
        bool confirmed
    }

    TYPOLOGY {
        string id PK
        string label
        string severity
        string description
    }
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | | Google AI API key for Gemini Embedding 2 |
| `GCS_BUCKET_NAME` | No | | Google Cloud Storage bucket for document storage |
| `CONTRADICTION_THRESHOLD` | No | `0.65` | Cosine similarity threshold below which cross-document section pairs are flagged |

## Demo Walkthrough (Fixture B)

Fixture B loads **Fixture Holdings Pty Ltd** with three deliberately inconsistent documents that produce three contradiction flags:

**Flag 1: Nominee Shareholder Concealment (Critical)**

The shareholder register lists Pacific Trust Services Pty Ltd holding 600 Ordinary shares with a note that it acts as nominee for an undisclosed beneficial owner. The constitution contains no nominee provisions section and explicitly denies nominee arrangements exist.

**Flag 2: Undisclosed Share Class (High)**

The ASIC extract records three share classes (Ordinary, Class B Preference, Class C Convertible Preference). The constitution authorises only two classes (Ordinary and Class B Preference) and states that no other class is authorised without a special resolution.

**Flag 3: Director Authority Inconsistency (High/Critical)**

The ASIC extract records James Mitchell as Sole Director with sole signatory authority and unlimited transaction authority. The constitution requires a quorum of two directors and mandates dual director approval for any transaction exceeding $50,000.

## Why a Shared Vector Space?

The core architectural decision is embedding all document modalities (PDF page images, extracted text, table content) through a single model (`gemini-embedding-2-preview`) into one 3072-dimensional vector space.

Cosine similarity between vectors from different documents is only meaningful when both vectors were produced by the same model with the same training. Gemini Embedding 2 is a natively multimodal embedding model that processes text, images, and mixed content through a unified encoder, producing vectors that share geometric structure. When we compute `cosine(ASIC_officeholder_embedding, constitution_director_embedding)`, the resulting similarity score reflects genuine semantic alignment because both vectors occupy the same learned manifold.

The alternative (separate text and vision models fused at score level) would not produce the same result. Each model would produce vectors in its own learned space. Cosine similarity between vectors from different models is mathematically undefined because the dimensions do not correspond. Score-level fusion (averaging similarity scores from separate models) loses the cross-modal geometric relationships that make contradiction detection work.

## Detection Approach

STRATUM uses a hybrid detection strategy that mirrors real production AML systems:

1. **Keyword-pattern detection** identifies candidate contradictions across document pairs. Corporate documents discussing the same topic (e.g. director authority) are always semantically similar, making pure threshold-based cosine similarity impractical for specific factual contradictions like sole vs dual director authority.

2. **Embedding-based typology matching** classifies each candidate against a FAISS index of AUSTRAC/FATF typology descriptions to name and explain the contradiction type.

3. **Cross-document cosine similarity** is reported as a distance metric showing how semantically different the two conflicting sections are.

## AUSTRAC/FATF Typologies

| ID | Label | Severity |
|----|-------|----------|
| `nominee_concealment` | Nominee Shareholder or Director Concealment | Critical |
| `layered_ownership` | Complex Layered Ownership Obscuring Control | High |
| `undisclosed_share_classes` | Inconsistent or Undisclosed Share Classes | High |
| `shelf_company_transfer` | Shelf Company Acquisition and Rapid Ownership Transfer | Medium |
| `trust_concealment` | Trust Structure Concealing Beneficial Ownership | Critical |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/demo?fixture=A\|B` | Load pre-embedded fixture documents |
| `POST` | `/upload/{doc_type}` | Upload a PDF (asic_extract, constitution, shareholder_register) |
| `GET` | `/matters/{id}/graph` | Ownership graph JSON (Cytoscape.js format) |
| `GET` | `/matters/{id}/contradictions` | List detected contradictions |
| `POST` | `/matters/{id}/generate-cdd` | Download CDD report as PDF |
| `WS` | `/ws/{id}` | Real-time graph and contradiction events |

## Tech Stack

- **Backend**: FastAPI, Pydantic, WebSockets
- **Embedding**: Gemini Embedding 2 (`gemini-embedding-2-preview`), 3072-dimensional shared multimodal vector space
- **Search**: FAISS (IndexFlatIP) for both per-matter document indexes and the typology index
- **PDF Processing**: pdf2image + pdfplumber for page rendering and text extraction
- **Report Generation**: WeasyPrint + Jinja2 for CDD PDF reports
- **Frontend**: React 18 (CDN, no build step), Cytoscape.js + dagre layout, Tailwind CSS
- **Deployment**: Docker, Cloud Run (australia-southeast1)

## Deployment

### Docker

```bash
docker build -t stratum -f backend/Dockerfile .
docker run -p 8080:8080 -e GEMINI_API_KEY=your-key stratum
```

### Cloud Run

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _GEMINI_API_KEY=your-key
```

## Limitations

- The `gemini-embedding-2-preview` model is in public preview and is not suitable for production workloads
- In-memory storage only: all matters and FAISS indexes are lost on server restart
- The fixture documents are synthetic, and real ASIC extracts have different formatting that would require parser adjustments
- Contradiction detection uses keyword patterns tuned to the fixture data, so production use would require broader pattern coverage
- No authentication or multi-tenancy: this is a single-user demo application

## Disclaimer

This application is a compliance analysis tool for demonstration purposes. It requires human review and is not an automated decision system. All findings should be independently verified by qualified legal and compliance professionals.

## License

MIT
