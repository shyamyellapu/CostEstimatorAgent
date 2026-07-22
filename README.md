# Cost Estimator AI Agent

An AI-powered cost estimation platform for the fabrication, EPC (Engineering, Procurement & Construction), structural steel, and piping industries. The system automates the full estimation workflow — from ingesting engineering drawings and BOQ documents to generating Excel costing sheets and Word quotation letters — with a multi-provider AI backbone and a Gmail-connected RFQ inbox.

---

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Backend Setup](#2-backend-setup)
  - [3. Frontend Setup](#3-frontend-setup)
  - [4. One-Command Launcher](#4-one-command-launcher)
- [Environment Variables](#environment-variables)
- [Database](#database)
- [AI Providers](#ai-providers)
- [Document Processing Pipeline](#document-processing-pipeline)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [Reference Files](#reference-files)

---

## Features

| Module | Description |
|---|---|
| **Drawing Costing** | Upload engineering drawings (PDF) → LlamaParse parses to markdown → LLM extracts BOM (steel, handrails, grating, bolts, paint) → deterministic costing engine → Excel Job Costing Sheet |
| **Estimate Workflow** | Multi-step: upload files → AI extraction → user confirmation → costing calculation → Excel download |
| **BOQ Parser** | Parse BOQ documents (Excel/PDF/DOCX) into structured line items |
| **RFQ Inbox** | Gmail OAuth2 integration — sync, classify, and auto-process incoming RFQ emails; validate, compare revisions, and promote to jobs |
| **Cover Letter Generator** | AI-drafted Word quotation letters using a company template with header/footer branding |
| **Weight Calculator** | Standalone steel section weight calculator |
| **Job History** | Full audit trail with revision history for all estimates |
| **Settings** | Live AI provider info, rate library, company branding configuration |
| **AI Chat** | Context-aware chat assistant (per-job or global) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                  │
│  Dashboard │ Drawing Costing │ Estimates │ RFQ Inbox │ Settings │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API (Axios)
┌───────────────────────────▼─────────────────────────────────────┐
│                     Backend (FastAPI + Python)                   │
│                                                                  │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │  API Routes    │  │  Costing Engine  │  │  AI Layer       │ │
│  │  (10 groups)   │  │  (deterministic) │  │  (5 providers)  │ │
│  └────────┬───────┘  └──────────────────┘  └────────┬────────┘ │
│           │                                          │           │
│  ┌────────▼───────┐  ┌──────────────────┐  ┌────────▼────────┐ │
│  │  Services      │  │  File Storage    │  │  LlamaParse     │ │
│  │  (25 modules)  │  │  Local/Azure/S3  │  │  (PDF → MD)     │ │
│  └────────┬───────┘  └──────────────────┘  └─────────────────┘ │
│           │                                                      │
│  ┌────────▼───────────────────────────────────────────────────┐ │
│  │              PostgreSQL (SQLAlchemy async + Alembic)        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │                              │
    Gmail API                    Azure Blob / AWS S3
  (RFQ ingestion)                (production storage)
```

---

## Tech Stack

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| React | 19 | UI framework |
| TypeScript | 5 | Type safety |
| Vite | 8 | Build tool and dev server |
| React Router DOM | 7 | Client-side routing |
| TanStack Query | 5 | Server state and caching |
| Axios | — | HTTP client |
| Recharts | — | Dashboard charts |
| Zustand | — | Client state management |
| React Dropzone | — | File upload zones |
| React Hot Toast | — | Notifications |
| Lucide React | — | Icon set |

### Backend

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11 | Runtime |
| FastAPI | 0.115 | Web framework |
| Uvicorn / Gunicorn | — | ASGI server |
| Pydantic v2 | — | Data validation and settings |
| SQLAlchemy | 2.0 | Async ORM |
| asyncpg | — | PostgreSQL async driver |
| Alembic | — | Database migrations |
| openpyxl | — | Excel generation |
| python-docx | — | Word document generation |
| PyMuPDF | — | PDF to image rendering |
| LlamaCloud SDK | — | LlamaParse document ingestion |
| instructor | — | Structured LLM output |

### Database

- **PostgreSQL 16** — only supported database (no SQLite fallback)
- JSONB columns for all AI payloads and extracted data

---

## Project Structure

```
CostEstimatorAgent/
├── backend/
│   ├── app/
│   │   ├── ai/                         # AI provider abstraction layer
│   │   │   ├── ai_provider.py          # Abstract base class + shared Pydantic models
│   │   │   ├── openai_provider.py      # OpenAI
│   │   │   ├── claude_provider.py      # Anthropic Claude (native PDF support)
│   │   │   ├── groq_provider.py        # Groq (Llama models)
│   │   │   ├── gemini_provider.py      # Google Gemini (OpenAI-compatible endpoint)
│   │   │   ├── openrouter_provider.py  # OpenRouter gateway
│   │   │   ├── prompts.py              # All LLM prompt templates
│   │   │   └── __init__.py             # get_ai_provider() factory
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── estimate.py         # Main estimate workflow
│   │   │       ├── drawing_costing.py  # Drawing upload → BOM → costing
│   │   │       ├── rfq.py              # RFQ CRUD and processing
│   │   │       ├── gmail.py            # Gmail OAuth2 and inbox sync
│   │   │       ├── boq.py              # BOQ document parsing
│   │   │       ├── cover_letter.py     # Word cover letter generation
│   │   │       ├── drawing.py          # Drawing extraction (vision)
│   │   │       ├── chat.py             # AI chat endpoint
│   │   │       ├── history.py          # Job history and audit
│   │   │       └── settings.py         # Rate configuration
│   │   ├── models/
│   │   │   └── __init__.py             # All SQLAlchemy ORM models
│   │   ├── services/                   # Business logic (25 modules)
│   │   │   ├── costing_engine.py       # Deterministic cost calculation
│   │   │   ├── drawing_costing.py      # Drawing-specific BOM costing
│   │   │   ├── llama_parser.py         # LlamaCloud SDK integration
│   │   │   ├── excel_generator.py      # .xlsx costing sheet writer
│   │   │   ├── cover_letter_service.py # Word quotation generator
│   │   │   ├── rfq_extractor.py        # RFQ AI extraction
│   │   │   ├── rfq_validation.py       # RFQ revision comparison
│   │   │   ├── gmail_service.py        # Gmail OAuth2 and sync
│   │   │   ├── file_storage.py         # Storage abstraction (local/Azure/S3)
│   │   │   └── ...                     # 15 more cost sub-modules
│   │   ├── tasks/
│   │   │   └── rfq_tasks.py            # Async background task worker
│   │   ├── config.py                   # Pydantic settings (all env vars)
│   │   ├── database.py                 # SQLAlchemy engine and session
│   │   └── main.py                     # App factory, router registration
│   ├── alembic/
│   │   └── versions/
│   │       ├── 0001_initial_postgresql.py
│   │       └── 0002_drawing_workflow.py
│   ├── storage/                        # Local file storage (gitignored)
│   │   ├── uploads/
│   │   ├── outputs/
│   │   ├── rfq_uploads/
│   │   └── llama_parsed/               # Cached LlamaParse markdown results
│   ├── logs/                           # Rotating log files (gitignored)
│   ├── .env.example
│   ├── requirements.txt
│   └── setup_db.ps1                    # Interactive PostgreSQL setup script
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts               # Axios instance (VITE_BACKEND_URL)
│   │   ├── pages/                      # 13 page components
│   │   ├── components/
│   │   │   ├── layout/                 # AppLayout, Sidebar, ChatFooter
│   │   │   └── rfq/                    # RFQ sub-components
│   │   ├── App.tsx                     # Route definitions
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── ReferenceFiles/
│   ├── MASTER FABRICATION Template.docx  # Cover letter base template
│   ├── Header and Footer.docx            # Company header/footer
│   └── Sample Job Costing Sheet.xlsx     # Excel output template
├── azure-pipelines.yml                   # Backend CI/CD → Azure App Service
├── azure-staticwebapp.yml                # Frontend CI/CD → Azure Static Web Apps
├── run.ps1                               # One-command local dev launcher
└── README.md
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Match exactly; 3.12 not tested |
| Node.js | 20+ | LTS recommended |
| PostgreSQL | 16+ | Must be running before backend start |
| Git | any | |
| Tesseract OCR (optional) | 5.x | Required only for image-based OCR fallback |

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/shyamyellapu/CostEstimatorAgent.git
cd CostEstimatorAgent
```

### 2. Backend Setup

```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
Copy-Item backend/.env.example backend/.env
# Edit backend/.env — set DATABASE_URL and at least one AI provider key

# Set up the database (Windows interactive helper)
cd backend
.\setup_db.ps1 -Action setup -DBName cost_estimator
cd ..

# Run migrations
cd backend
alembic upgrade head
cd ..

# Start the backend server
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.
Interactive Swagger docs: `http://localhost:8000/docs`

### 3. Frontend Setup

```powershell
cd frontend
npm install
npm run dev -- --port 5173 --host
```

Create `frontend/.env.local`:

```env
VITE_BACKEND_URL=http://localhost:8000
```

The app will be available at `http://localhost:5173`.

### 4. One-Command Launcher

On Windows, a single PowerShell script starts both services in separate windows:

```powershell
.\run.ps1
```

This opens:
- **Backend** → `http://localhost:8000`
- **Frontend** → `http://localhost:5173`

---

## Environment Variables

All backend variables go in `backend/.env`. A complete template is provided at `backend/.env.example`.

### Required

| Variable | Example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:pass@localhost:5432/cost_estimator` | PostgreSQL connection — must use `asyncpg` driver |
| `AI_PROVIDER` | `gemini` | Active AI provider: `openai` \| `claude` \| `groq` \| `openrouter` \| `gemini` |

At least **one** AI provider key is required:

| Provider | Key | Default Model |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| OpenRouter | `OPENROUTER_API_KEY` | `openai/gpt-oss-20b:free` |
| Gemini | `GEMINI_API_KEY` | `gemini-3.5-flash` |

### Document Parsing

| Variable | Description |
|---|---|
| `LLAMA_PARSE_API_KEY` | LlamaCloud API key — required for the drawing costing pipeline |

### Storage

| Variable | Default | Description |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` \| `azure` \| `s3` |
| `LOCAL_STORAGE_PATH` | `./storage` | Base path for local file storage |
| `AZURE_STORAGE_CONNECTION_STRING` | — | Azure Blob Storage connection string |
| `AZURE_CONTAINER_NAME` | `cost-estimator` | Azure container name |
| `AWS_ACCESS_KEY_ID` | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | — | AWS credentials |
| `AWS_BUCKET_NAME` | — | S3 bucket name |
| `AWS_REGION` | `us-east-1` | S3 region |

### AI Model Overrides (optional)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o` | Primary OpenAI model |
| `OPENAI_MODEL_FAST` | `gpt-4o-mini` | Fast OpenAI model (classification) |
| `OPENAI_MODEL_VISION` | `gpt-4o` | Vision model (drawing analysis) |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Primary Claude model |
| `CLAUDE_MODEL_DRAWING` | `claude-sonnet-4-6` | Drawing-specific Claude model |
| `CLAUDE_DRAWING_PDF_MODE` | `images` | `images` \| `native_pdf` \| `auto` |
| `CLAUDE_DRAWING_IMAGE_DPI` | `300` | DPI for PDF-to-image rendering |
| `CLAUDE_DRAWING_DENSE_DPI` | `400` | DPI for dense A0/A1 drawings |
| `MAX_LLM_PAGES_PER_BATCH` | `15` | Max pages per LLM batch |
| `GROQ_MODEL_LARGE` | `llama-3.3-70b-versatile` | Complex extraction model |
| `GROQ_MODEL_FAST` | `llama-3.1-8b-instant` | Fast classification model |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Gemini model |
| `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` | OpenRouter model |

### Gmail OAuth2

| Variable | Description |
|---|---|
| `GMAIL_CLIENT_ID` | Google Cloud OAuth2 client ID |
| `GMAIL_CLIENT_SECRET` | Google Cloud OAuth2 client secret |
| `GMAIL_REDIRECT_URI` | `http://localhost:5173/gmail/callback` |

### Company Branding

Used in generated cover letters and Excel headers.

| Variable | Example |
|---|---|
| `COMPANY_NAME` | `C&J Gulf Equipment Manufacturing LLC` |
| `COMPANY_ADDRESS` | `Musaffah, Abu Dhabi, UAE` |
| `COMPANY_PHONE` | `+971-XX-XXXXXXX` |
| `COMPANY_EMAIL` | `estimation@cnjgulf.com` |
| `COMPANY_WEBSITE` | `www.cnjgulf.com` |
| `SIGNATORY_NAME` | `Bilal Ahmed` |
| `SIGNATORY_TITLE` | `Cost & Estimation Engineer` |

### Reference File Paths

| Variable | Default |
|---|---|
| `DRAWING_COSTING_TEMPLATE_PATH` | `ReferenceFiles/Sample Job Costing Sheet.xlsx` |
| `COVER_LETTER_MASTER_TEMPLATE_PATH` | `ReferenceFiles/MASTER FABRICATION Template.docx` |
| `COVER_LETTER_HEADER_FOOTER_DOCX_PATH` | `ReferenceFiles/Header and Footer.docx` |

### Application

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `true` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000` | CORS allowed origins |
| `RFQ_CONFIDENCE_THRESHOLD` | `0.75` | Minimum confidence to auto-accept RFQ extractions |
| `RFQ_AUTO_EXTRACT` | `true` | Auto-trigger AI extraction on RFQ upload |
| `TASK_WORKER_MAX_CONCURRENT` | `3` | Max concurrent background RFQ tasks |

---

## Database

### Migrations

```bash
# Apply all pending migrations (run from backend/)
alembic upgrade head

# Check current migration state
alembic current

# Create a new migration after model changes
alembic revision --autogenerate -m "describe the change"

# Roll back one migration
alembic downgrade -1
```

### Key Tables

| Table | Description |
|---|---|
| `jobs` | All estimation jobs — status, total weight, total cost |
| `uploaded_files` | Every uploaded file with storage metadata |
| `extracted_data` | AI extraction results stored as JSONB |
| `costing_sheets` | Computed costing line items and totals |
| `bom_items` | Drawing costing BOM line items |
| `quantity_results` | Extracted quantity results per job |
| `rfq_records` | RFQ metadata and processing state |
| `rfq_emails` | Raw ingested Gmail messages |
| `rfq_attachments` | Attachments extracted from RFQ emails |
| `rfq_line_items` | Extracted and validated RFQ line items |
| `validation_results` | LLM validation results per RFQ |
| `gmail_credentials` | Per-user Gmail OAuth2 tokens |
| `rate_configurations` | Configurable cost rates (material, labour, etc.) |
| `chat_history` | Chat messages per session |
| `audit_logs` | Full audit trail for all job state changes |

---

## AI Providers

The AI layer is fully abstracted behind a single interface. Switch providers by changing one `.env` variable with no code changes.

```env
AI_PROVIDER=gemini   # openai | claude | groq | openrouter | gemini
```

### Provider Comparison

| Provider | Best For | Context Window | Notes |
|---|---|---|---|
| **OpenAI** (`gpt-4o`) | General extraction, vision | 128K | Most reliable |
| **Claude** (`claude-sonnet-4-6`) | Drawing analysis, long documents | 200K | Native PDF support; best for dense drawings |
| **Gemini** (`gemini-3.5-flash`) | High-volume extraction | 1M | Large context; good cost/performance ratio |
| **OpenRouter** | Free-tier testing | Varies | Routes to multiple backends |
| **Groq** | Speed-critical tasks | 30K TPM | 30K token per-minute limit — not suitable for large BOQs |

### Provider Architecture

```
get_ai_provider()  ←  AI_PROVIDER env var
        │
        ▼
 _make_provider()
        │
        ├── OpenAIProvider
        ├── ClaudeProvider
        ├── GroqProvider
        ├── GeminiProvider
        └── OpenRouterProvider
                │
                ▼ (all inherit)
           AIProvider (abstract base)
                ├── extract_from_document()
                ├── extract_from_image()
                ├── parse_boq()
                ├── classify_member()
                ├── parse_quotation()
                ├── draft_cover_letter()
                ├── chat()
                └── complete()
```

---

## Document Processing Pipeline

### Drawing Costing

```
PDF Upload
    │
    ▼
LlamaParse  (LlamaCloud agentic tier)
    │  ─── cached at storage/llama_parsed/<job_id>/<file>.md
    ▼
Markdown passed to LLM
    │  prompt: LLAMAPARSE_BOQ_EXTRACTION_PROMPT
    ▼
JSON extraction:
  { structural_steel, handrails, grating, bolts_m20x90, paint_material }
    │
    ▼
Deterministic costing engine
    │
    ▼
Excel Job Costing Sheet
  (stamped into ReferenceFiles/Sample Job Costing Sheet.xlsx template)
```

**Extracted quantities → Excel cell mapping:**

| Extracted Item | Excel Cell | Notes |
|---|---|---|
| Structural Steel (kg) | G23 | Direct write |
| Handrails (kg) | G24 | Direct write |
| Grating (kg) | G25 | Direct write |
| Paint Material (litres) | G26 | Direct write |
| Structural Welding qty | G30 | `steel_kg + handrail_kg` |
| Structural Fabrication qty | G31 | `steel_kg + handrail_kg` |
| Welding man-hours | I30 | Formula: `=INT((G30/1000)*40)` |
| Fabrication man-hours | I31 | Formula: `=INT((G31/1000)*80)` |
| Galvanizing Work (kg) | G40 | `handrail_kg` |
| Blasting area (m²) | G41 | Calculated surface area |
| Painting area (m²) | G42 | Calculated surface area |

### Handrail Weight Calculation

When a document lists handrail pipe by **linear meters** rather than kg, the system calculates weight automatically:

```
weight_kg = linear_m × kg_per_m
```

Standard pipe weights used:

| Pipe Size | kg/m |
|---|---|
| 25 NB | 3.38 |
| 32 NB | 4.05 |
| 42 NB | 5.41 (default) |
| 50 NB | 5.44 |
| 65 NB | 8.63 |

If pipe size is unknown, 5.41 kg/m (42 NB top rail) is used as the default. Both the LLM prompt and the backend code apply this fallback independently.

### LlamaParse Caching

Parsed markdown files are cached at `storage/llama_parsed/<job_id>/<filename>.md`. On subsequent runs with the same filename, the cache is used automatically — skipping the LlamaParse API call. This is the primary mechanism for fast development iteration.

---

## API Reference

**Base URL:** `http://localhost:8000`
**Interactive Swagger docs:** `http://localhost:8000/docs`

### System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Application health check |
| `GET` | `/health/db` | PostgreSQL connectivity check |
| `GET` | `/api/ai/info` | Active AI provider and model configuration |
| `GET` | `/api/company/info` | Company branding configuration |

### Estimates

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/estimate/upload` | Upload files (PDF/image/Excel/DOCX), create or append a job |
| `POST` | `/api/estimate/extract` | Trigger AI extraction on uploaded files |
| `POST` | `/api/estimate/confirm` | User confirms or edits extracted data |
| `POST` | `/api/estimate/calculate` | Run deterministic costing engine |
| `POST` | `/api/estimate/generate-excel` | Stream Excel costing sheet download |
| `GET` | `/api/estimate/jobs` | List all jobs |
| `GET` | `/api/estimate/jobs/{job_id}` | Get full job detail |

### Drawing Costing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/drawing-costing/analyse` | Upload drawing PDF → LlamaParse → LLM BOM → costing |
| `GET` | `/api/drawing-costing/{job_id}/review` | Get BOM items for review |
| `PATCH` | `/api/drawing-costing/{job_id}/bom-items/{item_id}` | Edit a BOM line item |
| `POST` | `/api/drawing-costing/{job_id}/recalculate` | Recalculate after BOM edits |
| `POST` | `/api/drawing-costing/{job_id}/approve` | Approve and lock the job |
| `POST` | `/api/drawing-costing/{job_id}/generate-excel` | Download Excel costing sheet |

### RFQ

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/rfq` | List all RFQs |
| `POST` | `/api/rfq/{rfq_id}/extract` | AI extraction of line items |
| `POST` | `/api/rfq/{rfq_id}/validate` | Validate extracted data |
| `GET` | `/api/rfq/{rfq_id}/validation` | Get validation results |
| `POST` | `/api/rfq/{rfq_id}/review` | Submit manual review |
| `POST` | `/api/rfq/{rfq_id}/approve` | Approve RFQ |
| `GET` | `/api/rfq/{rfq_id}/revisions/compare` | Compare two RFQ revisions |
| `POST` | `/api/rfq/{rfq_id}/convert-to-job` | Promote approved RFQ to an estimate job |
| `POST` | `/api/rfq/{rfq_id}/auto-costing` | One-click auto-costing from RFQ |
| `GET` | `/api/rfq/{rfq_id}/auto-costing/download-excel` | Download auto-costed Excel |

### Gmail

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/gmail/auth-url` | Get OAuth2 consent URL |
| `POST` | `/api/gmail/callback` | Exchange auth code for tokens |
| `GET` | `/api/gmail/mailboxes` | List connected mailboxes |
| `DELETE` | `/api/gmail/mailboxes/{id}` | Disconnect a mailbox |
| `POST` | `/api/gmail/sync` | Sync inbox and detect RFQ emails |
| `GET` | `/api/gmail/inbox` | List detected RFQ emails |
| `POST` | `/api/gmail/inbox/{id}/process` | Trigger processing for an email |

### Other

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/boq/parse` | Parse BOQ document into line items |
| `POST` | `/api/boq/export-csv` | Export parsed BOQ as CSV |
| `POST` | `/api/cover-letter/generate` | Generate Word cover letter |
| `POST` | `/api/cover-letter/parse-quotation` | Parse quotation text |
| `POST` | `/api/chat` | AI chat with optional job context |
| `GET` | `/api/chat/history` | Chat message history |
| `GET` | `/api/history` | Job list with audit trail |
| `GET` | `/api/settings` | Get rate library |
| `PUT` | `/api/settings` | Update rates |
| `POST` | `/api/settings/seed-defaults` | Reset rates to defaults |

---

## Deployment

### Azure (Production)

The repository includes Azure DevOps pipeline configurations for both services.

**Backend → Azure App Service**

Pipeline: `azure-pipelines.yml`

- Runtime: Python 3.11
- Server: Gunicorn with Uvicorn workers (`-k uvicorn.workers.UvicornWorker -w 4`)
- All `backend/.env` variables must be set as App Service application settings
- Set `STORAGE_BACKEND=azure` and configure `AZURE_STORAGE_CONNECTION_STRING`

**Frontend → Azure Static Web Apps**

Pipeline: `azure-staticwebapp.yml`

- Node.js 20, Vite build
- App location: `/frontend`, output location: `dist`
- Set `VITE_BACKEND_URL` to the production App Service URL in the Static Web App configuration

### Production Checklist

- [ ] `DATABASE_URL` points to a managed PostgreSQL instance
- [ ] `STORAGE_BACKEND=azure` with `AZURE_STORAGE_CONNECTION_STRING` set
- [ ] `SECRET_KEY` set to a long cryptographically random string
- [ ] `DEBUG=false`
- [ ] `ALLOWED_ORIGINS` contains the production frontend URL only
- [ ] `GMAIL_REDIRECT_URI` updated to the production frontend URL
- [ ] `ReferenceFiles/` directory deployed alongside the backend
- [ ] `alembic upgrade head` run against the production database before first start

---

## Reference Files

The `ReferenceFiles/` directory contains company-specific templates that drive Excel and Word output. All three files must be present on the server relative to the backend working directory.

| File | Purpose |
|---|---|
| `Sample Job Costing Sheet.xlsx` | Excel template for Job Costing Sheets. All formula cells, merged cells, and formatting are preserved — only specific data cells (G23–G45, I30–I31, etc.) are written by the engine. |
| `MASTER FABRICATION Template.docx` | Word template for cover letters and quotation letters. Contains the clause library and page layout. |
| `Header and Footer.docx` | Company letterhead header and footer injected into all generated Word documents. |

---

## Logs

The backend writes rotating log files to `backend/logs/app.log`:

- Maximum file size: 5 MB per file
- Backup count: 5 files retained
- Log format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

Full raw LLM responses are logged with `═══ RAW LLM RESPONSE ═══` delimiters for debugging extraction accuracy.

---

## External Integrations

| Service | Purpose | Required Key |
|---|---|---|
| OpenAI | AI extraction and vision | `OPENAI_API_KEY` |
| Anthropic Claude | AI extraction, drawing analysis | `ANTHROPIC_API_KEY` |
| Groq | Alternative fast LLM | `GROQ_API_KEY` |
| OpenRouter | OpenAI-compatible gateway (free models) | `OPENROUTER_API_KEY` |
| Google Gemini | Alternative AI provider | `GEMINI_API_KEY` |
| LlamaCloud / LlamaParse | Agentic document parsing (PDF → markdown) | `LLAMA_PARSE_API_KEY` |
| Gmail API | OAuth2 inbox sync, RFQ email ingestion | `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` |
| Azure Blob Storage | Production file storage | `AZURE_STORAGE_CONNECTION_STRING` |
| AWS S3 | Alternative file storage | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Azure App Service | Backend production hosting | `azure-pipelines.yml` |
| Azure Static Web Apps | Frontend production hosting | `azure-staticwebapp.yml` |

---

## License

Proprietary — C&J Gulf Equipment Manufacturing LLC. All rights reserved.
