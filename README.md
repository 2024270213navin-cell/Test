# 🤖 ServiceNow AI Automation

> AI-powered ticket resolution system: **ServiceNow → FastAPI → RAG (FAISS) → Ollama (Gemma) → Response**

---

## 📁 Project Structure

```
servicenow-ai/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory + lifespan
│   ├── config.py                  # Pydantic settings (env-driven)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py              # GET /health
│   │   ├── search.py              # POST /api/v3/search   ← ServiceNow endpoint
│   │   └── files.py               # File upload / ingest / delete
│   ├── core/
│   │   ├── __init__.py
│   │   ├── data_processor.py      # Excel ingestion & cleaning (DataProcessor)
│   │   ├── retriever.py           # FAISS semantic retrieval  (Retriever)
│   │   ├── prompt_generator.py    # Prompt construction        (PromptGenerator)
│   │   ├── response_generator.py  # Ollama API wrapper         (ResponseGenerator)
│   │   └── rag_pipeline.py        # Pipeline orchestrator      (RAGPipeline)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic request/response models
│   └── utils/
│       ├── __init__.py
│       ├── logger.py              # Loguru structured logging
│       ├── file_manager.py        # Upload directory management
│       └── servicenow_client.py   # ServiceNow REST API client
├── frontend/
│   └── app.py                     # Streamlit UI
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── tests/
│   ├── __init__.py
│   ├── test_core.py               # Unit tests (DataProcessor, PromptGenerator, schemas)
│   └── test_api.py                # Integration tests (FastAPI endpoints)
├── scripts/
│   └── generate_sample_kb.py      # Generates sample Excel knowledge base
├── data/
│   ├── faiss_index/               # Persisted FAISS index (auto-created)
│   ├── knowledge_base/            # Default KB storage
│   └── uploads/                   # Uploaded Excel files
├── logs/                          # Application logs (auto-created)
├── .env.example
├── .gitignore
├── Makefile
├── pytest.ini
├── README.md
└── requirements.txt
```

---

## 🧠 Architecture

```
ServiceNow
    │  POST /api/v3/search
    ▼
FastAPI Backend
    │
    ├─ Retriever ──────── FAISS (sentence-transformers: all-MiniLM-L6-v2)
    │      └─ top-k chunks
    │
    ├─ PromptGenerator ── Structures: system + context + history + question
    │
    └─ ResponseGenerator ─ Ollama POST /api/generate (gemma4:31b-cloud)
           └─ AI response text
    │
    ▼
SearchResponse { response, context[], model, latency_ms }
    │
    ▼
ServiceNow (work note / resolution update)
```

---

## ⚙️ Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.12+ |
| Ollama | latest |
| RAM | 32 GB+ recommended for Gemma 31B |
| Disk | 20 GB+ for model weights |

---

## 🚀 Setup Instructions

### 1. Clone & create virtual environment

```bash
git clone https://github.com/your-org/servicenow-ai.git
cd servicenow-ai

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate.bat     # Windows
```

### 2. Install dependencies

```bash
python.exe -m pip install --upgrade pip
pip install -r requirements.txt
# or: make install
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — at minimum update:
```dotenv
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your_password
OLLAMA_BASE_URL=http://localhost:11434
```

### 4. Install and start Ollama

```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama server
ollama serve

# Pull Gemma 31B model (in a new terminal — ~20 GB download)
ollama pull gemma4:31b-cloud

# Verify the model is available
ollama list
```

> **Tip — smaller model for testing:** Replace `gemma4:31b-cloud` with `gemma:7b` or `llama3:8b`
> in `.env` (`OLLAMA_MODEL=gemma:7b`) if you have limited RAM.

### 5. Generate sample knowledge base (optional)

```bash
python scripts/generate_sample_kb.py
# Creates: data/knowledge_base/sample_kb.xlsx (10 IT support Q&A rows)
```

---

## ▶️ Running the System

### Backend (FastAPI)

```bash
# Development (hot-reload)
make backend
# or
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Production
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
```

API is available at: **http://localhost:8000**  
Interactive docs: **http://localhost:8000/docs**

### Frontend (Streamlit)

```bash
# In a separate terminal
make frontend
# or
streamlit run frontend/app.py --server.port 8501
```

UI available at: **http://localhost:8501**

---

## 🐳 Docker Deployment

```bash
# Build and start all services
make docker-up
# or
docker compose -f docker/docker-compose.yml up --build -d

# View logs
docker compose -f docker/docker-compose.yml logs -f

# Stop
make docker-down
```

> **Note:** Ollama must run on the host machine. The containers connect via `host.docker.internal:11434`.

---

## 📡 API Reference

### `POST /api/v3/search` — ServiceNow Integration Endpoint

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
  "response": "To reset your VPN password:\n1. Navigate to https://vpn-portal.company.com\n2. Click 'Forgot Password'...",
  "context": [
    {
      "category": "VPN",
      "question": "How do I reset my VPN password?",
      "response": "Navigate to the VPN portal...",
      "reference_information": "KB0001",
      "similarity_score": 0.94
    }
  ],
  "model": "gemma4:31b-cloud",
  "latency_ms": 3421.5,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### `GET /health`

```json
{
  "status": "healthy",
  "ollama_reachable": true,
  "faiss_loaded": true,
  "indexed_chunks": 250,
  "version": "3.0.0"
}
```

### `POST /api/v3/files/upload`

```bash
curl -X POST http://localhost:8000/api/v3/files/upload \
  -F "file=@data/knowledge_base/sample_kb.xlsx"
```

### `POST /api/v3/files/{filename}/ingest`

```bash
curl -X POST http://localhost:8000/api/v3/files/sample_kb.xlsx/ingest
```

### `GET /api/v3/files`

```bash
curl http://localhost:8000/api/v3/files
```

---

## 🧪 Sample cURL / Postman Requests

### Full end-to-end search test:

```bash
# 1. Check health
curl http://localhost:8000/health | python -m json.tool

# 2. Upload the sample knowledge base
curl -X POST http://localhost:8000/api/v3/files/upload \
  -F "file=@data/knowledge_base/sample_kb.xlsx"

# 3. Ingest into FAISS
curl -X POST http://localhost:8000/api/v3/files/sample_kb.xlsx/ingest

# 4. Run a search query
curl -X POST http://localhost:8000/api/v3/search \
  -H "Content-Type: application/json" \
  -d '{
    "question": "My Outlook is not syncing emails",
    "key": "en",
    "history": []
  }' | python -m json.tool

# 5. Multi-turn search with history
curl -X POST http://localhost:8000/api/v3/search \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What if that does not work?",
    "key": "en",
    "history": [
      {"role": "user",      "content": "Outlook is not syncing"},
      {"role": "assistant", "content": "Try File → Account Settings → Repair..."}
    ]
  }' | python -m json.tool
```

---

## 🧪 Running Tests

```bash
# All tests
make test
# or
pytest tests/ -v

# Specific test file
pytest tests/test_core.py -v
pytest tests/test_api.py -v

# With coverage
pytest tests/ --cov=backend --cov-report=html
```

---

## 🔌 ServiceNow Integration

The system is designed to be called from ServiceNow Business Rules or Flow Designer.

### ServiceNow REST Message (outbound) example:

```javascript
// ServiceNow Script Include / Business Rule
var r = new RESTMessageV2();
r.setEndpoint('http://your-server:8000/api/v3/search');
r.setHttpMethod('POST');
r.setRequestHeader('Content-Type', 'application/json');

var body = {
    question: current.short_description + ' ' + current.description,
    key: 'en',
    history: []
};
r.setRequestBody(JSON.stringify(body));

var response = r.execute();
var aiResponse = JSON.parse(response.getBody());

// Update work notes on the incident
current.work_notes = '[AI Suggestion]\n' + aiResponse.response;
current.update();
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma4:31b-cloud` | Model name |
| `OLLAMA_TIMEOUT` | `120` | Request timeout (seconds) |
| `OLLAMA_TEMPERATURE` | `0.3` | LLM temperature |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `FAISS_TOP_K` | `5` | Retrieved context chunks |
| `FAISS_INDEX_PATH` | `./data/faiss_index` | Index persistence path |
| `UPLOAD_DIR` | `./data/uploads` | Excel upload directory |

---

## 🛠 Troubleshooting

| Problem | Solution |
|---|---|
| `Cannot connect to Ollama` | Run `ollama serve` in a terminal |
| `model not found` | Run `ollama pull gemma4:31b-cloud` |
| `FAISS index not loaded` | Upload + ingest an Excel file first via UI or API |
| `Ollama timeout` | Increase `OLLAMA_TIMEOUT` in `.env`; Gemma 31B is slow on CPU |
| `Missing columns` error | Ensure Excel has exactly: Category, Question, Response, Reference Information |
| Out of memory | Use `gemma:7b` or `llama3:8b` instead of `gemma4:31b-cloud` |
