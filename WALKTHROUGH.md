# Contract Analyzer - Technical Walkthrough

**5-10 Minute Presentation for Interview**

---

## Slide 1: Project Overview

**Contract Compliance Analyzer - Production MVP**

**Purpose:** Automate compliance analysis of third-party vendor contracts against 5 critical security requirements.

**Key Features:**
- PDF upload → Structured JSON output
- Evidence-first RAG architecture  
- Deterministic quote validation
- Dual LLM support (OpenAI / Ollama)

**Tech Stack:**
- **Backend:** Python, FastAPI, PyMuPDF, BM25, Pydantic
- **Frontend:** React, Vite
- **LLM:** OpenAI GPT-4 (external) or Ollama (local)

---

## Slide 2: Architecture - Evidence-First Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  PDF Contract Upload                                        │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Parse (PyMuPDF)                                         │
│     → Extract text per page                                 │
│     → Track char offsets for provenance                     │
│     → Detect OCR needs (scanned PDFs)                       │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Chunk (Page-Based)                                      │
│     → Break into chunks with page ranges                    │
│     → Normalize text (Unicode, whitespace)                  │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Retrieve (BM25)  ← FOR EACH OF 5 REQUIREMENTS           │
│     → Keyword-based scoring (deterministic)                 │
│     → Top-5 chunks per requirement                          │
│     → NEVER send full document to LLM ✓                     │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Analyze (LLM)                                           │
│     → Evidence-only prompts                                 │
│     → Schema-enforced JSON output                           │
│     → Rubric-based evaluation                               │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Validate (Deterministic)                                │
│     → Exact substring matching (normalized)                 │
│     → Remove hallucinated quotes                            │
│     → Adjust confidence (proportional penalty)              │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Structured JSON Output                                     │
│  ✓ 5 ComplianceResults (question, state, confidence,       │
│    quotes, rationale)                                       │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Decision:** Evidence-First = Cost-efficient + Reduced hallucination

---

## Slide 3: The 5 Compliance Requirements (Table 1)

| # | Requirement | Key Criteria |
|---|-------------|--------------|
| 1 | **Password Management** | Length/strength, no defaults, salted hashing, lockout, vaulting, break-glass rotation |
| 2 | **IT Asset Management** | Inventory (cloud, DB, tooling), fields defined, quarterly review, drift remediation |
| 3 | **Security Training & Background Checks** | Training on-hire + annually, screening policy, attestation |
| 4 | **Data in Transit Encryption** | TLS 1.2+, cert management, no weak ciphers, admin pathways covered |
| 5 | **Network AuthN/AuthZ** | SAML SSO, OAuth, MFA for privileged, bastion, RBAC, session logging |

**Output for Each:** Fully Compliant / Partially Compliant / Non-Compliant

---

## Slide 4: Quote Validation - The "Trust But Verify" Layer

**Problem:** LLMs hallucinate quotes ~15-30% of the time.

**Solution:** Deterministic Post-Processing

**Algorithm:**
1. **Normalize** (Unicode quotes → ASCII, collapse whitespace, lowercase)
2. **Exact substring match** against evidence chunks
3. **Map to page range** (try single chunk → adjacent pairs → fallback)
4. **Remove invalid quotes** + adjust confidence

**Example:**
```
LLM Output: "Passwords must be at least 12 characters long."
Evidence:   "...passwords must be at least 12 characters long..."
✓ VALID → Keep quote, page 5

LLM Output: "Annual penetration testing is required."
Evidence:   (not found in any retrieved chunks)
✗ INVALID → Remove quote, reduce confidence by 10%
```

**Result:** 100% of displayed quotes are verified verbatim from source.

---

## Slide 5: Confidence Scoring Methodology

**Initial Score (LLM-generated):**
- Rubric coverage (how many criteria explicitly found)
- Evidence strength (explicit "must" vs. vague "should")
- Contradiction detection

**Adjustments (Quote Validation):**
```python
# Proportional penalty for removed quotes
removed_count = original - validated
penalty = min(20%, removed_count × 10%)
final_confidence = max(20%, initial - penalty)

# Severe penalty if all quotes removed
if removed_count == original:
    final_confidence = min(initial, 30%)
```

**Ranges:**
- 90-100%: Very high (all criteria, validated quotes)
- 70-89%: High (most criteria, minor gaps)
- 50-69%: Moderate (some criteria, significant gaps)
- 30-49%: Low (few criteria, many quotes removed)
- 0-29%: Very low (minimal/no evidence)

**Transparency:** All adjustments logged + annotated in rationale.

---

## Slide 6: Key Tradeoffs & Design Decisions

| Decision | Tradeoff | Rationale |
|----------|----------|-----------|
| **BM25 vs. Vector DB** | BM25 (keyword) chosen over embeddings | Deterministic, no model dependency, fast, interpretable. Sufficient for compliance keywords. |
| **Page-based chunks** | Chunks = whole pages vs. fixed 400-char windows | Preserves document structure, simplifies page mapping, reduces cross-chunk quotes. |
| **Top-5 chunks only** | Risk: miss requirements in other pages | Cost-efficient, token-efficient. Mitigated by keyword-rich retrieval queries. |
| **In-memory job store** | Lost on restart vs. DB persistence | MVP simplicity. Documented path to DynamoDB/PostgreSQL for production. |
| **Deterministic validation** | Exact match only vs. fuzzy similarity | Auditability > recall. Legal context requires verbatim quotes. |
| **Dual LLM support** | Complexity vs. flexibility | Supports both cloud (faster, better quality) and local (cost-free, private). |

---

## Slide 7: Failure Modes & Robustness

**What We Handle:**
- ✅ **Scanned PDFs** → Detect low text density, flag `needs_ocr`, warn user
- ✅ **LLM hallucination** → Quote validator removes invalid quotes
- ✅ **Ambiguous language** → LLM trained to detect "should" vs. "must"
- ✅ **Missing requirements** → Returns "Non-Compliant" with low confidence
- ✅ **Large contracts** → Evidence-first keeps context under LLM token limits
- ✅ **API failures** → Retry logic (max 3 attempts), graceful error messages

**What We Don't Handle (MVP Scope):**
- ❌ OCR preprocessing (flagged but not executed)
- ❌ Multi-language contracts (English only)
- ❌ Image/table extraction (text-based analysis only)
- ❌ Complex layout parsing (multi-column, footnotes)

**Production Path:** AWS Textract for OCR, Claude 3.5 for vision, Vector DB for semantic search.

---

## Slide 8: Demo Flow (Live Walkthrough)

**1. Upload Contract PDF**
- Show UI: file selector → "Analyze Contract" button
- Backend receives PDF → creates job_id → returns 202 Accepted

**2. Status Polling (Real-Time)**
- Frontend polls `/api/v1/status/{job_id}` every 1.5s
- Show status panel:
  - ✅ Progress bar: 0% → 20% → 36% → ... → 100%
  - ✅ Stage text: "Parsing PDF" → "Analyzing requirement 3/5"
  - ✅ Timing: Total 15.2s (LLM 12.4s, Parse 850ms)

**3. Results Display**
- Table with 5 rows (one per requirement)
- Columns: Question | State | Confidence | Quotes | Rationale
- Expandable quotes with page numbers
- Color-coded badges (green/yellow/red)
- JSON viewer (collapsible)
- Metadata: LLM mode, model, OCR warning

**4. Walkthrough a Result**
- Pick one requirement (e.g., Password Management)
- Show: Fully Compliant, 92% confidence
- Expand quotes: 3 quotes with page ranges (5, 7, 12)
- Read rationale: explains why compliant
- Show JSON structure matches assignment schema

---

## Slide 9: Testing & Reproducibility

**Unit Tests:** 6 test files covering all pipeline stages
```bash
pytest backend/tests/ -v
# test_schemas.py - Pydantic validation
# test_parse_pdf.py - PDF extraction
# test_retriever.py - BM25 scoring, cross-chunk matching
# test_quote_validator.py - Unicode normalization, hallucination removal
# test_compliance_analyzer.py - LLM mock, JSON parsing
# test_job_processor.py - End-to-end orchestration
```

**Fresh Clone Test:**
```bash
git clone <repo>
cd contract-analyzer

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# (add OpenAI API key to .env)
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# Upload sample PDF → Verify output
```

**All dependencies pinned** in requirements.txt and package.json.

---

## Slide 10: Production Readiness & Next Steps

**Current State: Production-Oriented MVP**
- ✅ Clean architecture (interfaces, separation of concerns)
- ✅ Comprehensive error handling
- ✅ Structured logging (no sensitive data)
- ✅ Schema validation (Pydantic)
- ✅ Quote auditability (deterministic validation)
- ✅ Dual LLM support
- ✅ Documentation (README, ARCHITECTURE, API_TESTING, CONFIDENCE_SCORING)
- ✅ Tests (unit + integration)

**Production Migration Path:**

| Component | MVP (Local) | Production (AWS) |
|-----------|-------------|------------------|
| **Storage** | In-memory dict | DynamoDB (jobs) + S3 (PDFs) |
| **Queue** | FastAPI BackgroundTasks | SQS + Lambda/ECS workers |
| **LLM** | OpenAI API | AWS Bedrock (Claude 3.5) |
| **OCR** | Flag only | AWS Textract |
| **Vector DB** | BM25 (no DB) | OpenSearch / Pinecone |
| **Logging** | Local logs | CloudWatch Logs + X-Ray |
| **Secrets** | .env file | AWS Secrets Manager |
| **Auth** | None (demo) | Cognito + API Gateway |
| **Scaling** | Single uvicorn | ECS Fargate (auto-scale) |

**Estimated Migration Effort:** 2-3 weeks for production-grade deployment.

---

## Slide 11: Questions & Deep Dives

**Ready to discuss:**
- ✅ Architecture alternatives (why BM25 not embeddings?)
- ✅ Prompt engineering strategies (few-shot, chain-of-thought?)
- ✅ Handling edge cases (what if contract has contradictions?)
- ✅ Scalability (how to handle 1000 contracts/day?)
- ✅ Cost optimization (token usage per contract?)
- ✅ Accuracy evaluation (how to measure without ground truth?)
- ✅ Security considerations (PII handling, data retention?)

**Code Walkthrough Available:**
- Pipeline stages (parse → chunk → retrieve → analyze → validate)
- Quote validator logic (normalization + substring matching)
- LLM client abstraction (external/local switching)
- Job orchestration (async processing + progress tracking)

---

## Thank You

**Repository:** [GitHub Link]  
**Live Demo:** http://localhost:5173 (React UI)  
**API Docs:** http://localhost:8000/docs (Swagger UI)

**Documentation:**
- `README.md` - Quick start, environment setup
- `backend/ARCHITECTURE.md` - Technical deep dive
- `backend/CONFIDENCE_SCORING.md` - Scoring methodology
- `backend/API_TESTING.md` - curl examples, security audit

**Contact:** [Your Name] | [Email]
