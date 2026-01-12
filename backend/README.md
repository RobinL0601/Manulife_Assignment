# Contract Analyzer Backend

Evidence-first contract compliance analysis system built with FastAPI.

## Overview

This system analyzes legal contracts for compliance with 5 security requirements:
1. Password management policies
2. IT asset management and tracking
3. Security training and background checks
4. TLS/SSL for data in transit
5. Authentication and authorization protocols

## Architecture

### Data Flow

```
PDF Upload → Parse (PyMuPDF) → Chunk → Retrieve Evidence → LLM Analysis → Validate Quotes → Results
```

### Core Components

**Data Models** (`app/core/schemas.py`)
- `DocumentArtifact` / `PageArtifact` - Canonical document representation with character offsets
- `Chunk` / `EvidenceChunk` - Text chunks with page provenance
- `ComplianceResult` - Structured output with validated quotes

**Pipeline** (`app/pipeline/`)
- `PDFParser` - Extract text per page with PyMuPDF
- `PageBasedChunker` - Page-based chunking (MVP strategy)
- Interfaces for `IRetriever`, `IComplianceAnalyzer`, `IQuoteValidator` (TODO)

**LLM Abstraction** (`app/services/llm_client.py`)
- `ExternalLLMClient` - OpenAI fully implemented
- `LocalLLMClient` - Ollama/vLLM support
- Factory: `get_llm_client()` configured via environment

## Setup

### Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

Copy `env.example` to `.env`:

```env
LLM_MODE=external
EXTERNAL_API_PROVIDER=openai
EXTERNAL_API_KEY=sk-...
EXTERNAL_MODEL=gpt-4
```

For local LLM (Ollama):
```env
LLM_MODE=local
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_MODEL=llama3
```

### Running

```bash
uvicorn app.main:app --reload --port 8000
```

API Documentation: http://localhost:8000/docs

## API Endpoints

All endpoints prefixed with `/api/v1`:

**POST /upload** - Upload PDF contract
- Accepts: `multipart/form-data` with PDF file (max 10MB)
- Returns: `{job_id, status}`

**GET /status/{job_id}** - Check processing status
- Returns: `{status, progress, ...}`

**GET /result/{job_id}** - Get compliance results
- Returns: `{results: [ComplianceResult, ...]}`
- Status 425 if still processing

**GET /health** - Health check

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Environment configuration
│   ├── api/routes.py        # REST endpoints
│   ├── core/
│   │   ├── schemas.py       # Pydantic models
│   │   └── storage.py       # Job store
│   ├── services/
│   │   └── llm_client.py    # LLM abstraction
│   ├── pipeline/
│   │   ├── interfaces.py    # Pipeline contracts
│   │   ├── parse_pdf.py     # PDF parser
│   │   └── chunker.py       # Chunking strategies
│   └── utils/
│       ├── text_normalizer.py
│       ├── logger.py
│       └── exceptions.py
└── tests/
    ├── test_schemas.py
    └── test_parse_pdf.py
```

## Development

### Testing

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

### Implementation Status

✅ **Complete**:
- FastAPI application with API routes
- PDF parsing with page provenance (PyMuPDF)
- Chunking with page/character tracking
- LLM client abstraction (OpenAI functional)
- Data models and validation
- Text normalization

🚧 **TODO**:
- BM25 retrieval service
- Compliance analyzer with LLM prompting
- Quote validator with deterministic matching
- Background job processing integration

## Design Principles

**Evidence-First**: LLM receives only top-k retrieved chunks, never full documents

**Deterministic Validation**: Quotes validated via exact substring matching after normalization

**Page Provenance**: All text tracked to source pages via character offsets

**MVP Scope**: Digital PDFs only (no OCR, tables, or multi-column layouts)

## Notes

- **Storage**: In-memory (replace with Redis/PostgreSQL for production)
- **LLM Provider**: OpenAI functional, Anthropic stubbed for future
- **Chunking**: Page-based recommended for contracts, fixed-size available
