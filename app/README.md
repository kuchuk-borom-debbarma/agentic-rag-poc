# AWS Customer Agreement RAG App

This is the clean final assessment app. It is self-contained under `app/`, including the RAG source PDF, backend, frontend, docs, and runtime defaults.

## Architecture

```text
React frontend
  -> FastAPI backend
      -> RAG ingestion internals
          -> layout-aware PDF block loader
          -> hierarchical parser
          -> semantic chunker with cached embeddings
      -> RAG query service
          -> query planning
          -> semantic retrieval
          -> evidence expansion
          -> prompt builder
          -> chat client
          -> SQLite query logger
      -> analytics service
          -> SQLite analytics repository
      -> evaluation service
          -> 30-case benchmark runs without analytics logging
          -> retrieval, answer, and system quality metrics
          -> SQLite evaluation history
```

The backend follows interface-first design. Services depend on contracts from `assessment_app/interfaces/`, while concrete adapters live in `assessment_app/infra/`.

## Backend Setup

From `app/backend/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn assessment_app.main:app --reload
```

The API runs at `http://localhost:8000`.

## Frontend Setup

From `app/frontend/`:

```bash
npm install
cp .env.example .env
npm run dev
```

The UI runs at `http://localhost:5173`.

## Model Configuration

The backend uses OpenAI-compatible HTTP endpoints for embeddings and chat. Configure both separately in `app/backend/.env`.

```bash
OPENAI_EMBEDDING_BASE_URL=http://localhost:11434/v1
OPENAI_EMBEDDING_MODEL=qwen3-embedding:4b
OPENAI_EMBEDDING_API_KEY=

OPENAI_CHAT_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_CHAT_MODEL=google/gemma-4-31b-it
OPENAI_CHAT_API_KEY=your-api-key
```

Any provider that exposes `/embeddings` and `/chat/completions` can be swapped in through config.

## API Flow

1. `POST /api/v1/ingest` rebuilds configured PDF ingestion data into SQLite graph maps and the dedicated RAG Chroma collection.
2. `POST /api/v1/ask` plans retrieval queries, retrieves semantic matches, expands evidence with exact sections, neighbor chunks, and referenced sections, asks the chat model to answer only from evidence, returns answer plus sources, and logs usage to SQLite.
3. `GET /api/v1/analytics` returns SQL-backed usage metrics for the dashboard.
4. `POST /api/v1/evaluation/runs` runs the 30-case benchmark through the same query path without analytics logging and stores the run in SQLite.
5. `GET /api/v1/evaluation/runs` and `GET /api/v1/evaluation/runs/{run_id}` show previous benchmark runs and per-case details.

## Ingestion Rebuild

Stage 1 owns prototype-aligned layout extraction and hierarchical-aware parsing. Stage 2 owns semantic chunking with cached embeddings. Stage 3 owns lightweight SQLite graph maps for hierarchy, sequence, ownership, and references. Stage 4 persists chunk vectors in a dedicated Chroma collection and exposes `POST /api/v1/ingest`.

The current ingestion internals build `Section` layout, `ChunkedContent` records, `GraphMaps` navigation data, and Chroma vector records keyed by graph chunk ID. SQLite is used for graph-map persistence because Stage 3 needs simple map lookups, not a Docker-backed graph server.

## Retrieval Strategy

Default `top_k` is `5`.

Why:
- It gives enough evidence for most direct questions about the AWS agreement.
- It keeps the answer prompt compact.
- It is easy to explain and tune in the demo.

The app also expands retrieved evidence with one neighbor chunk by default (`DEFAULT_NEIGHBORS=1`) and exact section lookup when the query mentions a section number.

## Analytics

Every successful `/ask` call is logged to SQLite with:

- query
- answer
- answer found flag
- response latency
- source snippets
- timestamp

`GET /analytics` returns:

- total query count
- answer-found rate
- average response latency
- most frequently asked questions
- queries where no answer was found

## Benchmark Evaluation

The Evaluation tab runs a 30-case AWS Customer Agreement benchmark through the real RAG query flow and stores previous runs.

Metric groups:

- Retrieval: expected section recall/precision, evidence found, source count, dedupe rate.
- Answer: expected answer overlap, answer-found accuracy, citation section accuracy, unsupported-answer check.
- System: average latency, p95 latency, context volume, pass rate, total run latency.

Evaluation requests do not write to normal query analytics. Evaluation run summaries and per-case results are stored in SQLite evaluation tables.

Detailed flow and current limits live in `app/evaluation/evaluation-flow.md`.

## Seed Demo Queries

After ingesting the document, run at least 30 test queries:

```bash
python scripts/seed_queries.py
```

This fills the analytics dashboard with realistic data.

## Useful Commands

Backend syntax check:

```bash
python -m compileall assessment_app
```

Backend tests:

```bash
pip install -r requirements-dev.txt
pytest
```

Frontend build:

```bash
npm run build
```
