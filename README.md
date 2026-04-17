# 🤖 AI Support Automation

> FastAPI RAG pipeline — **Excel KB → ChromaDB → sentence-transformers → NVIDIA LLM → response**  
> Python 3.11+ · Render-ready · pip-only install (no C++ compilation)

---

## 📁 Project Structure

```
render_deploy/
├── backend/
│   ├── main.py                    # FastAPI app factory + lifespan
│   ├── config.py                  # Pydantic settings (env-driven)
│   ├── api/
│   │   ├── health.py              # GET /health
│   │   ├── search.py              # GET /api/v3/ask  · POST /api/v3/search
│   │   └── files.py               # Upload / ingest / delete / preview
│   ├── core/
│   │   ├── data_processor.py      # Excel ingestion & cleaning
│   │   ├── retriever.py           # ChromaDB semantic retrieval
│   │   ├── prompt_generator.py    # Prompt construction
│   │   ├── response_generator.py  # NVIDIA LLM wrapper
│   │   └── rag_pipeline.py        # Pipeline orchestrator
│   ├── models/
│   │   └── schemas.py             # Pydantic request/response models
│   └── utils/
│       ├── logger.py              # Loguru structured logging
│       └── file_manager.py        # Upload directory management
├── frontend/
│   └── app.py                     # Streamlit UI
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── tests/
│   ├── test_core.py
│   └── test_api.py
├── scripts/
│   └── generate_sample_kb.py      # Generates sample Excel knowledge base
├── data/
│   ├── chroma_db/                 # ChromaDB persistence (auto-created)
│   ├── knowledge_base/            # Default KB storage
│   └── uploads/                   # Uploaded Excel files
├── .env.example
├── render.yaml
├── Makefile
└── requirements.txt
```

---

## 🧠 Architecture

```
Client / ServiceNow
    │  POST /api/v3/search
    ▼
FastAPI Backend
    │
    ├─ Retriever ──────── ChromaDB (cosine similarity)
    │      │                └─ embeddings: sentence-transformers all-MiniLM-L6-v2
    │      └─ top-k context chunks
    │
    ├─ PromptGenerator ── system prompt + context + history + question
    │
    └─ ResponseGenerator ─ NVIDIA /v1/chat/completions  (google/gemma-3-27b-it)
           └─ AI response text
    │
    ▼
SearchResponse { response, context[], model, latency_ms }
```

---

## ⚙️ Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| NVIDIA API key | [build.nvidia.com](https://build.nvidia.com) |

No Ollama, no Docker, no GPU required for local development.

---

## 🚀 Local Setup

### 1. Clone & virtualenv

```bash
git clone https://github.com/your-org/ai-support.git
cd ai-support

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate.bat     # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Minimum required values in `.env`:

```dotenv
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
```

Everything else has sensible defaults.

### 4. Generate sample knowledge base (optional)

```bash
python scripts/generate_sample_kb.py
# Creates: data/knowledge_base/sample_kb.xlsx
```

### 5. Run

```bash
# Development (hot-reload)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# or
make backend
```

- API: **http://localhost:8000**
- Swagger docs: **http://localhost:8000/docs**

---

## ☁️ Render Deployment

### One-click via `render.yaml`

The repo includes a `render.yaml`. Connect the repo in the Render dashboard and it auto-configures.

Set these env vars manually in the Render dashboard (marked `sync: false`):

| Key | Value |
|---|---|
| `NVIDIA_API_KEY` | your key from build.nvidia.com |

Everything else is set in `render.yaml`.

### Disk persistence (optional but recommended)

ChromaDB writes its index to `./data/chroma_db`. Render's default filesystem is ephemeral — the index is lost on each deploy/restart. To persist it across deploys:

1. Add a **Render Disk** mount at `/data/chroma_db`
2. Set `CHROMA_PERSIST_DIR=/data/chroma_db` in env vars

No code changes needed.

---

## 📡 API Reference

### `GET /health`

```json
{
  "status": "healthy",
  "nvidia_reachable": true,
  "faiss_loaded": true,
  "indexed_chunks": 250,
  "version": "3.0.0"
}
```

> `faiss_loaded` reflects ChromaDB collection status (field name preserved for contract compatibility).

---

### `GET /api/v3/ask?q=...`

Direct question to NVIDIA LLM — no KB retrieval.

```bash
curl "http://localhost:8000/api/v3/ask?q=How+do+I+reset+my+VPN+password"
```

```json
{
  "question": "How do I reset my VPN password?",
  "answer": "...",
  "model": "google/gemma-3-27b-it",
  "latency_ms": 1240.5
}
```

---

### `POST /api/v3/search`

Full RAG pipeline — retrieves KB context, then calls NVIDIA LLM.

**Request:**
```json
{
  "question": "How do I reset my VPN password?",
  "key": "en",
  "history": [
    {"role": "user",      "content": "I cannot connect to VPN"},
    {"role": "assistant", "content": "Can you describe the error message?"}
  ]
}
```

**Response:**
```json
{
  "response": "To reset your VPN password: ...",
  "context": [
    {
      "category": "VPN",
      "question": "How do I reset my VPN password?",
      "response": "Navigate to the VPN portal...",
      "reference_information": "KB0001",
      "similarity_score": 0.94
    }
  ],
  "model": "google/gemma-3-27b-it",
  "latency_ms": 2340.5,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

---

### `POST /api/v3/files/upload`

Upload an Excel knowledge-base file (`.xlsx`).

```bash
curl -X POST http://localhost:8000/api/v3/files/upload \
  -F "file=@data/knowledge_base/sample_kb.xlsx"
```

**Required Excel columns** (case-insensitive):

| Column | Description |
|---|---|
| `Category` | Topic grouping |
| `Question` | The support question |
| `Response` | The answer |
| `Reference Information` | Optional KB article ID etc. |

---

### `POST /api/v3/files/{filename}/ingest`

Generate embeddings and load into ChromaDB.

```bash
curl -X POST http://localhost:8000/api/v3/files/sample_kb.xlsx/ingest
```

```json
{
  "filename": "sample_kb.xlsx",
  "chunks_indexed": 250,
  "message": "Successfully indexed 250 knowledge chunks from 'sample_kb.xlsx'."
}
```

---

### `GET /api/v3/files`

List all uploaded files and their ingest status.

---

### `DELETE /api/v3/files/{filename}`

Delete an uploaded file from disk.

---

### `GET /api/v3/files/{filename}/preview`

Preview first 50 rows of a file.

---

## 🧪 End-to-End Test (cURL)

```bash
# 1. Health check
curl http://localhost:8000/health | python -m json.tool

# 2. Upload KB
curl -X POST http://localhost:8000/api/v3/files/upload \
  -F "file=@data/knowledge_base/sample_kb.xlsx"

# 3. Ingest into ChromaDB
curl -X POST http://localhost:8000/api/v3/files/sample_kb.xlsx/ingest

# 4. Search
curl -X POST http://localhost:8000/api/v3/search \
  -H "Content-Type: application/json" \
  -d '{"question": "My Outlook is not syncing emails", "key": "en", "history": []}' \
  | python -m json.tool
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `NVIDIA_API_KEY` | *(required)* | NVIDIA API key |
| `NVIDIA_MODEL` | `google/gemma-3-27b-it` | LLM model name |
| `NVIDIA_MAX_TOKENS` | `512` | Max response tokens |
| `NVIDIA_TEMPERATURE` | `0.20` | LLM temperature |
| `NVIDIA_TIMEOUT` | `60` | Request timeout (seconds) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` or `cuda` |
| `CHROMA_PERSIST_DIR` | `./data/chroma_db` | ChromaDB storage path |
| `RETRIEVER_TOP_K` | `5` | Context chunks retrieved per query |
| `KNOWLEDGE_BASE_DIR` | `./data/knowledge_base` | Default KB directory |
| `UPLOAD_DIR` | `./data/uploads` | Uploaded file directory |
| `ALLOWED_ORIGINS` | `*` | CORS origins |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 🧪 Running Tests

```bash
pytest tests/ -v

# With coverage
pytest tests/ --cov=backend --cov-report=html
```

---

## 🐳 Docker

```bash
# Start all services
docker compose -f docker/docker-compose.yml up --build -d

# Logs
docker compose -f docker/docker-compose.yml logs -f

# Stop
docker compose -f docker/docker-compose.yml down
```

---

## 🛠 Troubleshooting

| Problem | Solution |
|---|---|
| `ChromaDB collection not loaded` | Upload + ingest an Excel file first |
| `LLM service error` | Check `NVIDIA_API_KEY` is set and valid |
| `Missing columns` error | Excel must have: Category, Question, Response, Reference Information |
| Index lost after Render restart | Add a Render Disk mounted at `CHROMA_PERSIST_DIR` |
| Slow first request | Embedding model downloads on first use (~90 MB) — subsequent requests are fast |

---

## 🔄 Migrating from FAISS version

Old `data/faiss_index/` files (`index.faiss`, `metadata.pkl`) are not used.
After deploying, simply re-ingest your Excel file via `/api/v3/files/{filename}/ingest`.
No data format changes — same Excel, same API contracts.
