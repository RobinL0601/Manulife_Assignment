# Contract Analyzer - Deployment Guide

## ✅ System Complete - Ready for Demo

### Pre-Flight Checklist

**Backend:**
- [x] All pipeline stages implemented (Parse, Chunk, Retrieve, Analyze, Validate)
- [x] 38 unit/integration tests
- [x] Zero linter errors
- [x] Logging is secure (no PII/contract text)
- [x] Error handling at all stages
- [x] API documentation at /docs

**Frontend:**
- [x] Upload interface
- [x] Status polling (1.5s)
- [x] Results table with expandable quotes
- [x] Error handling

## Quick Demo Setup (2 Minutes)

**Terminal 1 - Backend:**
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Browser:** http://localhost:3000

## Environment Setup

**Minimal .env (for demo with OpenAI):**
```env
LLM_MODE=external
EXTERNAL_API_KEY=sk-your-openai-key
EXTERNAL_MODEL=gpt-4
```

**Alternative (Ollama for local demo):**
```env
LLM_MODE=local
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_MODEL=llama3
```

## Test with Sample Contract

**Create test PDF:**
```python
import fitz

doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), """
SECURITY REQUIREMENTS CONTRACT

1. PASSWORD POLICY
All user passwords must be at least 12 characters long.
Passwords must include uppercase, lowercase, numbers, and special characters.
Multi-factor authentication (MFA) is required for all accounts.

2. ASSET MANAGEMENT
All IT assets must be tracked in the central inventory system.
Quarterly reconciliation of all assets is mandatory.

3. TRAINING REQUIREMENTS
Annual security awareness training is required for all employees.
Background checks must be completed before granting system access.

4. ENCRYPTION REQUIREMENTS
All data in transit must use TLS 1.2 or higher encryption.
Certificate management procedures must be documented.

5. ACCESS CONTROL
Single sign-on (SSO) with SAML must be implemented.
Role-based access control (RBAC) is required for all systems.
Session logging must be enabled for all privileged access.
""")
doc.save("demo_contract.pdf")
doc.close()
print("Created demo_contract.pdf")
```

**Expected Results:**
- All 5 requirements: "Fully Compliant"
- High confidence (80-95%)
- Multiple validated quotes per requirement
- Total processing time: 30-60 seconds

## Verification Commands

```bash
# 1. Upload
curl -X POST http://localhost:8000/api/v1/upload -F "file=@demo_contract.pdf"

# 2. Check status (use returned job_id)
curl http://localhost:8000/api/v1/status/{job_id}

# 3. Get results (when status=completed)
curl http://localhost:8000/api/v1/result/{job_id}
```

## Production Deployment

**Docker (Recommended):**
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# frontend/Dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - LLM_MODE=external
      - EXTERNAL_API_KEY=${OPENAI_API_KEY}
  
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
```

## Monitoring in Production

**Key Metrics to Track:**
- Upload success rate
- Processing time (P50, P95, P99)
- LLM API latency
- Quote validation rate (% quotes validated)
- Confidence score distribution
- Error rate by stage

**Alerts:**
- Processing time > 2 minutes
- Error rate > 5%
- Quote validation rate < 70%

## Known Limitations (MVP Scope)

1. **In-Memory Storage** - Jobs lost on restart (migrate to Redis/PostgreSQL)
2. **Single Process** - No horizontal scaling (add job queue)
3. **No OCR** - Scanned PDFs flagged only (add Textract)
4. **Simple PDF Layout** - No table extraction (add Camelot)
5. **No Authentication** - Open API (add JWT)

## Success Criteria

**System is working correctly if:**
- ✅ Upload returns job_id within 1 second
- ✅ Status polling shows progress 10% → 100%
- ✅ Results contain exactly 5 ComplianceResult objects
- ✅ Quotes have page_start/page_end and validated=true
- ✅ Confidence scores > 30% for valid contracts
- ✅ Logs show metadata only (no contract text)

**Demo-Ready!** 🚀
