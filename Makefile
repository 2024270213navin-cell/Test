# ─────────────────────────────────────────────
#  ServiceNow AI Automation — Makefile
# ─────────────────────────────────────────────

.PHONY: help install env backend frontend test docker-up docker-down clean

help:
	@echo ""
	@echo "  ServiceNow AI Automation — Dev Commands"
	@echo "  ─────────────────────────────────────────"
	@echo "  make install      Install Python dependencies"
	@echo "  make env          Copy .env.example → .env"
	@echo "  make backend      Start FastAPI backend (port 8000)"
	@echo "  make frontend     Start Streamlit frontend (port 8501)"
	@echo "  make test         Run pytest test suite"
	@echo "  make docker-up    Start all services via Docker Compose"
	@echo "  make docker-down  Stop Docker Compose services"
	@echo "  make clean        Remove __pycache__ and .pytest_cache"
	@echo ""

install:
	pip install --upgrade pip
	pip install -r requirements.txt

env:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; \
	else echo ".env already exists"; fi

backend:
	python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	streamlit run frontend/app.py --server.port 8501

test:
	pytest tests/ -v

docker-up:
	docker compose -f docker/docker-compose.yml up --build -d

docker-down:
	docker compose -f docker/docker-compose.yml down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
