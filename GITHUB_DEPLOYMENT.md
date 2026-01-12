# GitHub Deployment & Hosting Guide

## Step 1: Push to GitHub

### Initialize and Commit

```bash
# Navigate to project root
cd Manulife

# Initialize git (if not already done)
git init

# Add all files (respects .gitignore)
git add .

# Verify what will be committed (should NOT include venv, node_modules, .env)
git status

# First commit
git commit -m "Contract Analyzer - Production MVP

Core Features:
- Evidence-first RAG compliance analysis (5 requirements)
- Deterministic quote validation with page provenance
- Dual LLM support (OpenAI external / Ollama local)
- Real-time progress tracking with timing metrics

Bonus Features:
- Chat over contracts (evidence-based Q&A)
- Verified quotes with page numbers
- Variable confidence scoring

Technical:
- FastAPI + React architecture
- 31+ unit/integration tests
- Comprehensive documentation
- GitHub Actions CI/CD
"

# Create GitHub repository (via GitHub.com)
# Then add remote:
git remote add origin https://github.com/YOUR_USERNAME/contract-analyzer.git

# Push to main branch
git branch -M main
git push -u origin main
```

---

## Step 2: Hosting Options

### Option A: Free Full-Stack Deployment (Recommended for Demo)

**Use Render.com (Free Tier):**

**1. Deploy Backend:**
- Go to https://render.com (sign in with GitHub)
- Click "New +" → "Web Service"
- Connect your GitHub repo
- Settings:
  - **Name:** contract-analyzer-api
  - **Root Directory:** `backend`
  - **Environment:** Python 3
  - **Build Command:** `pip install -r requirements.txt`
  - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port 10000`
- Add Environment Variables:
  - `LLM_MODE=external`
  - `EXTERNAL_API_KEY=<your-openai-key>`
  - `EXTERNAL_MODEL=gpt-4`
- Click "Create Web Service"
- Note the URL: `https://contract-analyzer-api.onrender.com`

**2. Deploy Frontend:**
- Click "New +" → "Static Site"
- Connect same GitHub repo
- Settings:
  - **Name:** contract-analyzer
  - **Root Directory:** `frontend`
  - **Build Command:** `npm ci && npm run build`
  - **Publish Directory:** `dist`
- **Important:** Update `frontend/vite.config.js`:
  ```javascript
  server: {
    proxy: {
      '/api': {
        target: 'https://contract-analyzer-api.onrender.com', // Your backend URL
        changeOrigin: true,
      }
    }
  }
  ```
- Click "Create Static Site"
- Your app will be live at: `https://contract-analyzer.onrender.com`

**Cost:** $0/month (Free tier)  
**Limitations:** Backend sleeps after 15 min inactivity (cold start ~30s)

---

### Option B: Railway.app (Even Easier)

**One-Click Deploy:**
- Go to https://railway.app
- Click "Start a New Project" → "Deploy from GitHub repo"
- Select your repo
- Railway auto-detects FastAPI backend + React frontend
- Add environment variables:
  - `EXTERNAL_API_KEY=<your-key>`
  - `LLM_MODE=external`
- Deploy takes ~5 minutes
- Get public URLs for both frontend and backend

**Cost:** $0/month (500 hours free tier)

---

### Option C: GitHub Pages (Frontend Only - Limited Demo)

**Warning:** This only hosts the static frontend. Backend won't work.

```bash
# Build frontend for production
cd frontend
npm run build

# Install gh-pages (if not already)
npm install --save-dev gh-pages

# Add to package.json:
"scripts": {
  "deploy": "gh-pages -d dist"
},
"homepage": "https://YOUR_USERNAME.github.io/contract-analyzer"

# Deploy to GitHub Pages
npm run deploy

# Enable in GitHub repo settings:
# Settings → Pages → Source: gh-pages branch
```

**Result:** Static frontend at `https://YOUR_USERNAME.github.io/contract-analyzer`  
**Limitation:** API calls will fail (no backend)

**Use Case:** Visual demonstration only, no actual analysis

---

### Option D: Full Cloud Deployment (Production)

**AWS (Most Professional):**
- Frontend: S3 + CloudFront
- Backend: ECS Fargate or Lambda
- LLM: AWS Bedrock
- Storage: DynamoDB + S3
- Queue: SQS

**Estimated Cost:** ~$50-100/month  
**Setup Time:** 2-3 hours

**DigitalOcean App Platform (Simple):**
- Deploy both frontend + backend from one repo
- Auto-detects Python + Node.js
- Free tier available ($0 for static sites, $5/month for backend)

---

## Step 3: Make Repository Public

### On GitHub.com:

1. Go to your repository
2. Click "Settings"
3. Scroll to "Danger Zone"
4. Click "Change visibility" → "Make public"
5. Type repository name to confirm

---

## Step 4: Add Repository Description & Topics

### Repository Description (GitHub):
```
Contract compliance analyzer using evidence-first RAG. 
Dual LLM support (OpenAI/Ollama). React UI with real-time progress. 
Bonus: Chat over contracts.
```

### Topics (GitHub):
```
fastapi, react, openai, rag, llm, contract-analysis, 
compliance, document-processing, python, typescript
```

---

## 🎯 Recommended for Interview

**Best Option: Render.com Free Tier**

**Why:**
- ✅ Full-stack deployment (backend + frontend both work)
- ✅ Free tier sufficient for demo
- ✅ Public URL to share with interviewer
- ✅ Easy to set up (< 30 minutes)
- ✅ Auto-deploys on git push
- ✅ HTTPS included

**Setup Time:** 20-30 minutes  
**Cost:** $0  
**Result:** Live demo at `https://contract-analyzer.onrender.com`

---

## 📧 Share with Interviewer

**Email Template:**

```
Subject: Contract Analyzer Assignment - Completed

Hi [Interviewer Name],

I've completed the Contract Analyzer assignment. Here are the links:

📦 GitHub Repository: https://github.com/YOUR_USERNAME/contract-analyzer
🌐 Live Demo: https://contract-analyzer.onrender.com
📄 Walkthrough Slides: [Link to WALKTHROUGH.md in repo]

Key Features:
✓ Evidence-first RAG (Parse→Chunk→Retrieve→Analyze→Validate)
✓ 5 compliance requirements (exact Table 1 wording)
✓ Deterministic quote validation with page provenance
✓ Dual LLM support (OpenAI/Ollama)
✓ Real-time progress tracking + timing metrics
✓ Bonus: Chat over contracts with verified quotes
✓ 31+ unit/integration tests

Documentation:
- README.md - Quick start
- WALKTHROUGH.md - 11-slide technical presentation
- backend/ARCHITECTURE.md - Deep dive
- backend/CONFIDENCE_SCORING.md - Scoring methodology

Local Setup (5 minutes):
See README.md for step-by-step instructions.

Looking forward to discussing the architecture and design decisions!

Best regards,
[Your Name]
```

---

## ⚡ Quick Deploy Commands

### Push to GitHub
```bash
git add .
git commit -m "Production-ready Contract Analyzer MVP"
git push
```

### Deploy to Render (if using)
1. Sign up at https://render.com with GitHub
2. New Web Service → Connect repo → backend/
3. New Static Site → Connect repo → frontend/
4. Add EXTERNAL_API_KEY in environment variables
5. Done! Live in 10 minutes

---

## ✅ Final Checklist

Before sharing with interviewer:

- [ ] Pushed to GitHub (public repository)
- [ ] README.md has clear setup instructions
- [ ] Live demo URL works (if deployed)
- [ ] Can upload PDF and see results
- [ ] Chat feature works (bonus)
- [ ] Walkthrough slides ready
- [ ] Prepared to explain architecture

**Status: READY TO SHARE** 🚀
