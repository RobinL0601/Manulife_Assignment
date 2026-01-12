# Contract Analyzer - Architecture

## System Overview

Evidence-first contract compliance analysis system built with FastAPI and LLM integration.

## Core Principles

1. **Canonical Data Format**: `DocumentArtifact` with `PageArtifact` objects maintains page provenance throughout pipeline
2. **Evidence-First**: LLM receives only top-k retrieved evidence chunks, never full document
3. **Deterministic Validation**: Exact substring matching (no fuzzy logic) for quote verification
4. **Provider Abstraction**: LLM client interface supports external (OpenAI) and local (Ollama) modes

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                  │
│  POST /upload  |  GET /status/{id}  |  GET /result/{id} │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    Core Layer                            │
│  - Job Management (storage.py)                           │
│  - Data Models (schemas.py)                              │
│  - Configuration (config.py)                             │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                  Pipeline Layer                          │
│                                                           │
│  IParser → IChunker → IRetriever → IAnalyzer → IValidator│
│                                                           │
│  [PDFParser] → [PageBasedChunker] → [BM25Retriever] → [ComplianceAnalyzer] → [QuoteValidator]│
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                   Service Layer                          │
│  - LLM Client (OpenAI, Ollama)                           │
│  - Text Normalizer                                       │
│  - Logging & Exceptions                                  │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

```
PDF Upload
    ↓
PDFParser.parse() → DocumentArtifact
    ├─ pages: List[PageArtifact]
    │   ├─ page_number, raw_text, normalized_text
    │   └─ char_offset_start, char_offset_end
    └─ metadata: {parser_used, needs_ocr, ...}
    ↓
PageBasedChunker.chunk() → List[Chunk]
    ├─ chunk_id, text, normalized_text
    ├─ page_start, page_end
    └─ char_range: (start, end)
    ↓
BM25Retriever.retrieve(requirement_id, chunks, top_k=5) → List[EvidenceChunk]
    ├─ Scores chunks using BM25Okapi algorithm
    ├─ Uses curated keyword queries per requirement
    └─ Returns top-k chunks with relevance_score
    ↓
ComplianceAnalyzer.analyze(requirement_id, evidence) → ComplianceResult
    ├─ Build prompt with rubric + evidence chunks (with page labels)
    ├─ LLM generates JSON response (temperature=0.3 for consistency)
    ├─ Parse JSON to ComplianceResult schema
    ├─ If parse fails: retry once with "fix JSON" prompt
    ├─ If still fails: fallback (Non-Compliant, confidence=10, rationale="Model output could not be parsed")
    └─ Returns: compliance_state, confidence, quotes (unvalidated), rationale
    ↓
QuoteValidator.validate_quotes(result, evidence, doc) → Validated ComplianceResult
    ├─ Deterministic normalization (lowercase, quotes, dashes, whitespace)
    ├─ Exact substring match against evidence chunks
    ├─ Map quotes to page ranges from evidence chunks
    ├─ Drop hallucinated quotes (log warning with prefix only)
    └─ If all quotes invalid: reduce confidence ≤30, update rationale
```

## Key Components

### 1. Document Artifact (Canonical Format)

```python
DocumentArtifact
├── doc_id: UUID
├── filename: str
├── page_count: int
├── pages: List[PageArtifact]
│   ├── page_number: int (1-indexed)
│   ├── raw_text: str
│   ├── normalized_text: str
│   ├── char_offset_start: int
│   ├── char_offset_end: int
│   └── word_count: int
└── metadata: Dict
    ├── parser_used: "PyMuPDF"
    ├── needs_ocr: bool
    └── avg_chars_per_page: int
```

**Purpose**: Single source of truth for document structure and content. All pipeline stages operate on this canonical format.

### 2. Chunking Strategy

**PageBasedChunker** (MVP choice):
- Chunks by page or small page ranges
- Preserves document structure (sections, pages)
- Configurable: `pages_per_chunk`, `overlap_pages`
- Best for contracts where compliance requirements reference specific sections

### 3. LLM Abstraction

```python
LLMClient (Abstract)
├── ExternalLLMClient
│   └── OpenAI (fully implemented)
└── LocalLLMClient
    └── Ollama/vLLM (HTTP API)
```

**Configuration via env vars**:
- `LLM_MODE=external|local`
- `EXTERNAL_API_KEY`, `EXTERNAL_MODEL`
- `LOCAL_LLM_BASE_URL`, `LOCAL_MODEL`

### 4. Pipeline Interfaces

All pipeline stages implement abstract interfaces for testability and extensibility:

- `IParser`: PDF bytes → DocumentArtifact
- `IChunker`: DocumentArtifact → List[Chunk]
- `IRetriever`: (query, chunks) → List[EvidenceChunk]
- `IComplianceAnalyzer`: (question, evidence) → ComplianceResult
- `IQuoteValidator`: (quotes, document) → Validated quotes

## Compliance Analysis Schema

```json
{
  "compliance_question": "Does the contract require password management policies?",
  "compliance_state": "Fully Compliant",
  "confidence": 85,
  "relevant_quotes": [
    {
      "text": "All passwords must be at least 12 characters...",
      "page_start": 5,
      "page_end": 5,
      "validated": true
    }
  ],
  "rationale": "Section 3.2 explicitly requires password policies...",
  "evidence_chunks_used": ["doc_uuid:chunk_5", "doc_uuid:chunk_12"]
}
```

**5 Compliance Requirements** (hardcoded):
1. Password management policies (complexity, length, rotation)
2. IT asset management and tracking procedures
3. Security awareness training and background checks
4. TLS/SSL for data in transit
5. Authentication and authorization protocols (MFA, SSO, RBAC)

## Job Processing (Async)

```python
Job States: PENDING → PROCESSING → COMPLETED | FAILED

Job Workflow:
1. POST /upload → create job (PENDING)
2. Background task:
   - Parse PDF → DocumentArtifact
   - Chunk document → List[Chunk]
   - For each compliance question:
     * Retrieve top-5 evidence chunks
     * Call LLM with evidence (not full doc)
     * Parse response to ComplianceResult
     * Validate quotes against DocumentArtifact
   - Update job: results, status=COMPLETED
3. GET /result/{job_id} → return results
```

**Storage**: In-memory dict for MVP (replace with Redis/PostgreSQL for production).

## Text Normalization (Deterministic)

```python
TextNormalizer.normalize(text):
1. Unicode normalization (NFC)
2. Lowercase
3. Collapse whitespace (spaces, tabs, newlines → single space)
4. Strip leading/trailing whitespace
5. Remove zero-width characters
```

**Purpose**: Enable exact substring matching for quote validation without false negatives from formatting differences.

## Error Handling

Custom exception hierarchy:
```
ContractAnalyzerError
├── JobNotFoundError
├── JobNotCompletedError
├── InvalidFileError
└── ProcessingError

PipelineError
├── ParserError
├── ChunkerError
├── RetrieverError
├── AnalyzerError
└── ValidatorError

LLMClientError
```

## Configuration

Environment variables (`.env`):
```bash
# LLM Mode
LLM_MODE=external  # external | local

# External LLM (OpenAI)
EXTERNAL_API_PROVIDER=openai
EXTERNAL_API_KEY=sk-...
EXTERNAL_MODEL=gpt-4

# Local LLM (Ollama)
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_MODEL=llama3

# Processing
RETRIEVAL_TOP_K=5
CHUNK_SIZE=400
CHUNK_OVERLAP=100
MAX_UPLOAD_SIZE_MB=10
```

## Production Considerations

**Current State** (MVP):
- ✅ In-memory job storage
- ✅ Single-process deployment
- ✅ Simple PDF extraction (digital PDFs only)
- ✅ No OCR (flagged for future)
- ✅ Single chunking strategy

**Production Upgrades**:
- Persistent storage (Redis for jobs, PostgreSQL for results)
- Distributed job queue (Celery, RQ)
- OCR integration (Tesseract, AWS Textract)
- Table extraction (Camelot, Tabula)
- Caching layer (parsed documents, embeddings)
- Rate limiting and authentication
- Monitoring and observability (Prometheus, Datadog)

## Testing Strategy

**Unit Tests**:
- Data models (Pydantic validation)
- PDF parsing with mock documents
- Chunking logic
- Text normalization

**Integration Tests** (future):
- Full pipeline with real PDFs
- LLM mocking for deterministic tests
- Quote validation end-to-end

**Performance Tests** (future):
- Large document processing (100+ pages)
- Concurrent job handling
- Memory profiling

## File Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   ├── api/
│   │   └── routes.py        # API endpoints
│   ├── core/
│   │   ├── schemas.py       # Pydantic models
│   │   └── storage.py       # In-memory job store
│   ├── pipeline/
│   │   ├── interfaces.py    # Abstract interfaces
│   │   ├── parse_pdf.py     # PDF parser
│   │   └── chunker.py       # Page-based chunker
│   ├── services/
│   │   └── llm_client.py    # LLM abstraction
│   └── utils/
│       ├── text_normalizer.py
│       ├── logger.py
│       └── exceptions.py
├── tests/
│   ├── test_schemas.py
│   └── test_parse_pdf.py
├── requirements.txt
├── README.md
└── ARCHITECTURE.md          # This file
```

## Dependencies

Core dependencies:
- `fastapi` - Web framework
- `pydantic` - Data validation
- `PyMuPDF` - PDF parsing
- `rank-bm25` - Text retrieval (future)
- `httpx` - Async HTTP client for LLM APIs
- `pytest` - Testing

## Summary

This architecture prioritizes:
1. **Simplicity**: Clear interfaces, single responsibility
2. **Traceability**: Page provenance from PDF → chunks → quotes → results
3. **Testability**: Interface-based design, dependency injection
4. **Extensibility**: Easy to add new chunkers, retrievers, LLM providers
5. **Production-readiness**: Structured logging, error handling, async processing

MVP focuses on core functionality with clean architecture that scales to production requirements.
