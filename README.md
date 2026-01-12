# Contract Analyzer - Production MVP

Evidence-first compliance analysis system analyzing legal contracts for 5 security requirements: **Password Management**, **IT Asset Management**, **Security Training**, **TLS Encryption**, and **Authentication/Authorization**.

## Architecture

**Evidence-First Pipeline:**
```
PDF Upload → Parse (PyMuPDF) → Chunk (Page-Based) → Retrieve (BM25, top-5) → 
Analyze (LLM) → Validate (Deterministic) → Structured JSON Results
```

**Key Design Principles:**
- **Evidence-First**: LLM receives only top-5 BM25-scored chunks per requirement (never full document)
- **Schema Validation**: Pydantic-enforced `ComplianceResult`![architecture](https://github.com/user-attachments/assets/79c17adf-11f9-4edd-9f19-151f90c92327)
 with exact enum values
- **Deterministic Quote Grounding**: Exact substring matching after normalization (lowercase, collapse whitespace, normalize quotes/dashes)
- **Page Provenance**: Character offsets tracked from PDF → Chunks → Quotes → Results
- **Dual LLM Mode**: External (OpenAI) or Local (Ollama) via config

## Quick Start (5 Minutes)

**Admin**
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

**Backend:**
```bash
cd backend
python -m venv manulife
manulife\Scripts\activate  # Windows | source venv/bin/activate (Mac/Linux)
pip install -r requirements.txt
cp env.example .env  # Configure LLM settings (see below)
uvicorn app.main:app --reload --port 8000
```
→ API: http://localhost:8000/docs

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```
→ UI: http://localhost:3000

### Environment Configuration

**External LLM (OpenAI) - Recommended:**
```bash
LLM_MODE=external
EXTERNAL_API_PROVIDER=openai
EXTERNAL_API_KEY=sk-your-key-here
EXTERNAL_MODEL=gpt-4
```

**Local LLM (Ollama) - Development/Privacy:**
```bash
LLM_MODE=local
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_MODEL=llama3
# Note: Run `ollama pull llama3` first
```

## System Behavior & Failure Modes

### Normal Flow
1. Upload PDF → Job created (status: `pending`)
2. Background processing starts → Status: `processing`, progress: 10% → 100%
3. Analysis complete → Status: `completed`, 5 `ComplianceResult` objects returned

### Failure Modes

**Scanned/Image PDF (needs_ocr=true):**
- ✅ System proceeds with analysis
- ⚠️ Results will have low confidence (<30%)
- ⚠️ Metadata includes `needs_ocr: true` flag
- 📝 Log: "Document may need OCR (avg chars/page: X)"
- **Behavior**: No OCR performed in MVP; flagged for offline processing

**Invalid PDF / Parsing Failure:**
- ❌ Job status: `failed`
- Error message: "Processing failed: PDF parsing failed"
- HTTP 500 on GET /result

**LLM Hallucinated Quotes:**
- ✅ QuoteValidator drops invalid quotes
- ✅ If all quotes invalid: confidence reduced to ≤30
- ✅ Rationale appended: "No verifiable verbatim quotes found in retrieved evidence"

**Malformed LLM JSON:**
- ✅ Retry once with "fix JSON" prompt
- ✅ If still fails: fallback (`Non-Compliant`, confidence=10, rationale="Model output could not be parsed")

## Security & Compliance

### Data Protection
- ✅ **No contract text in logs** - Only metadata (job_id, page_count, file_size)
- ✅ **No prompts in logs** - LLM interactions not logged
- ✅ **No evidence text in logs** - Only chunk counts and scores
- ✅ **Quote validation failures** - Logs only 30-char prefix, never full quote
- ✅ **Error messages** - Generic, no data leakage

### Recommended Practices
- **Data Retention**: Delete jobs after 24 hours (implement cron job)
- **API Keys**: Use environment variables, never commit to git
- **Rate Limiting**: Add per-IP limits in production (e.g., 10 uploads/hour)
- **Authentication**: Add JWT tokens for multi-tenant deployments
- **HTTPS**: Mandatory for production (use reverse proxy like Nginx)

## Output Schema

```json
{
  "compliance_question": "Does the contract require password management policies?",
  "compliance_state": "Fully Compliant",  // "Partially Compliant" | "Non-Compliant"
  "confidence": 85,  // 0-100
  "relevant_quotes": [
    {"text": "verbatim quote", "page_start": 5, "page_end": 5, "validated": true}
  ],
  "rationale": "Section 3.2 explicitly requires password policies...",
  "evidence_chunks_used": ["uuid:chunk_5"]
}
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + Vite | UI with real-time polling |
| Backend | FastAPI + Pydantic | Async API with validation |
| PDF Parsing | PyMuPDF | Page-level text extraction |
| Retrieval | BM25 (rank-bm25) | Keyword scoring (5 curated queries) |
| LLM | OpenAI API / Ollama | Compliance analysis |
| Storage | In-memory dict | MVP job store |

## Testing

```bash
cd backend
pytest tests/ -v  # 38 unit/integration tests
```

**Coverage**: Parsing, chunking, retrieval, analysis (mocked LLM), validation, job orchestration


## Project Structure

```
contract-analyzer/
├── backend/         # FastAPI app, 15 Python modules, 38 tests
├── frontend/        # React UI, 6 files
├── README.md        # This file
└── .gitignore
```

**Documentation:**
- `backend/README.md` - Backend details
- `backend/ARCHITECTURE.md` - Technical deep-dive
- `backend/API_TESTING.md` - curl test commands

**License**: MIT - Open source for portfolio/interview use
