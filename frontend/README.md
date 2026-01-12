# Contract Analyzer - Frontend

Minimal React UI for contract compliance analysis.

## Features

- ✅ PDF file upload
- ✅ Real-time job status polling (1.5s interval)
- ✅ Compliance results table with 5 requirements
- ✅ Expandable quotes with page references
- ✅ Error handling
- ✅ Clean, minimal UI

## Setup

### Prerequisites

- Node.js 16+ and npm
- Backend server running on http://localhost:8000

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

The app will start on http://localhost:3000

The Vite dev server is configured to proxy `/api` requests to the backend at http://localhost:8000

### Build for Production

```bash
npm run build
```

Output will be in `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Usage

1. **Upload Contract**: Select a PDF file and click "Analyze Contract"
2. **Wait for Processing**: Status updates automatically via polling
3. **View Results**: Table shows 5 compliance requirements with:
   - Compliance state (color-coded)
   - Confidence score (0-100%)
   - Quotes (expandable with page references)
   - Rationale

## API Integration

Frontend calls these backend endpoints:

- `POST /api/v1/upload` - Upload PDF
- `GET /api/v1/status/{job_id}` - Poll status (every 1.5s)
- `GET /api/v1/result/{job_id}` - Fetch results when complete

## Project Structure

```
frontend/
├── src/
│   ├── main.jsx          # React entry point
│   ├── App.jsx           # Main app component
│   ├── App.css           # Component styles
│   └── index.css         # Global styles
├── index.html            # HTML template
├── vite.config.js        # Vite configuration with proxy
├── package.json          # Dependencies
└── README.md             # This file
```

## Technology Stack

- **React** 18 - UI library
- **Vite** 5 - Build tool and dev server
- **Native Fetch API** - HTTP requests (no axios needed)

## No Extra Features

This is a **minimal MVP** - intentionally excludes:
- ❌ Export functionality
- ❌ Chat interface
- ❌ ETA display
- ❌ Authentication
- ❌ Dark mode
- ❌ Multi-file upload

Focus is on core functionality only.
