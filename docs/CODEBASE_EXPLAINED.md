# Codebase Explained

This document explains the clean final assessment app under `app/`. The app is self-contained: its RAG source PDF, backend, frontend, docs, and runtime defaults live under `app/`.

## What This App Does

The app answers questions about one source document:

```text
app/resources/AWS Customer Agreement.pdf
```

It provides:

- a FastAPI backend
- a React frontend
- a Chroma vector store
- SQLite usage logging
- SQL-backed analytics
- benchmark evaluation metrics, history, and UI

Main user flow:

```text
user opens React app
-> clicks Ingest
-> backend parses PDF, detects sections, creates graph-aware chunks, embeds chunks, stores them in Chroma
-> user asks a question
-> backend plans retrieval branches and expands evidence around relevant chunks
-> backend asks chat model to answer only from retrieved context
-> backend returns answer and source snippets
-> backend logs query to SQLite
-> analytics dashboard reads SQL aggregates
-> evaluation tab runs benchmark cases without analytics logging
```

## Why The Codebase Is Split This Way

The project follows `app/CODEBASE_RULE.md`.

Important rule:

```text
routes -> services -> interfaces -> infra
```

Meaning:

- routes expose HTTP endpoints
- services own business flow
- interfaces define replaceable contracts
- infra implements concrete external systems

Routes do not contain RAG logic. Services do not know if storage is Chroma, FAISS, Neo4j, or something else. Infra can be replaced without rewriting the main flow.

This is similar to Spring-style dependency inversion:

```text
RagQueryService depends on VectorStore interface
ChromaVectorStore implements VectorStore
```

So later:

```text
ChromaVectorStore -> FaissVectorStore
```

should mostly change wiring and infra, not service flow.

## Top-Level Layout

```text
app/
  AGENTS.md
  README.md
  CODEBASE_EXPLAINED.md
  evaluation/
  resources/
  backend/
  frontend/
```

### `app/AGENTS.md`

Local DOX contract for final app code.

It says:

- final app lives here
- runtime RAG/query behavior must not depend on code or files outside `app/`
- RAG source PDFs live inside `app/resources/`
- runtime data stays ignored
- code must follow `app/CODEBASE_RULE.md`

### `app/README.md`

User-facing setup and run guide:

- backend install/run
- frontend install/run
- model env config
- API flow
- chunking strategy
- analytics behavior
- benchmark evaluation flow
- verification commands

### `app/CODEBASE_EXPLAINED.md`

This file. It is for walkthrough, onboarding, and explaining architecture in interview/demo.

## Backend Layout

```text
app/backend/
  requirements.txt
  requirements-dev.txt
  .env.example
  assessment_app/
    main.py
    interfaces/
    infra/
    services/
    routes/
    schemas/
    models/
  scripts/
  tests/
```

The backend is the core project. It exposes API endpoints and runs the RAG, logging, analytics, and evaluation flows.

## App Resources

```text
app/resources/
  AGENTS.md
  AWS Customer Agreement.pdf
```

This is the final app's local source-material folder.

Why it exists:

- the final app should not depend on resources outside `app/`
- cloning or copying `app/` should preserve the RAG source document
- backend defaults can point to app-local data

Default backend config:

```text
PDF_PATH=../resources/AWS Customer Agreement.pdf
```

## Backend Entry Point

File:

```text
app/backend/assessment_app/main.py
```

This creates the FastAPI app:

```text
create_app()
-> load config
-> configure CORS for React dev server
-> include health, ingest, ask, analytics, evaluation routes
```

It exports:

```python
app = create_app()
```

Run with:

```bash
uvicorn assessment_app.main:app --reload
```

## Config

File:

```text
app/backend/assessment_app/infra/config.py
```

Config is loaded from:

```text
app/backend/.env
```

Example file:

```text
app/backend/.env.example
```

Important env vars:

```text
PDF_PATH
CHROMA_DIR
CHROMA_COLLECTION
SQLITE_PATH
GRAPH_SQLITE_PATH
CHUNK_SIZE
CHUNK_OVERLAP
DEFAULT_TOP_K
DEFAULT_NEIGHBORS
OPENAI_EMBEDDING_BASE_URL
OPENAI_EMBEDDING_MODEL
OPENAI_EMBEDDING_API_KEY
OPENAI_CHAT_BASE_URL
OPENAI_CHAT_MODEL
OPENAI_CHAT_API_KEY
```

Why config lives in infra:

- env/filesystem concerns are external-system concerns
- services should not directly read environment variables
- swapping config style later should not affect routes or services

## Domain Models

File:

```text
app/backend/assessment_app/models/domain.py
```

Contains simple dataclasses used inside backend services.

### `DocumentBlock`

Represents one extracted PDF layout block:

```text
text
box_class
page_start
page_end
```

Created by:

```text
PdfDocumentLoader
```

Used by:

```text
HierarchicalAwareParser
```

### `DocumentChunk`

Represents one chunk that can be embedded and retrieved:

```text
chunk_id
text
page_start
page_end
source_file
section_id
section_number
section_title
parent_section_id
parent_section_number
parent_section_title
order
previous_chunk_id
next_chunk_id
referenced_section_ids
```

Created by:

```text
future indexing stage
```

Stored by:

```text
ChromaVectorStore
```

### `SourceSnippet`

Represents one retrieved source shown to the user:

```text
chunk_id
text
page_start
page_end
source_file
section_id
section_number
section_title
parent section fields
order
referenced_section_ids
source_type
score
```

Created by:

```text
ChromaVectorStore search and evidence expansion methods
```

Returned by:

```text
POST /ask
```

### `RetrievalQuery` and `QueryPlan`

Represent the planned query branches before retrieval:

```text
original query
Q1 original question
Q2/Q3 isolated branches when question is multi-part
exact target sections
whether references should be followed
```

Created by:

```text
QueryPlanner
```

### `QueryLogEntry`

Represents one query log row before writing to SQLite:

```text
query
answer
answer_found
latency_ms
sources_json
```

Created by:

```text
RagQueryService
```

Saved by:

```text
SqliteQueryLogger
```

## Evaluation Models

File:

```text
app/backend/assessment_app/services/evaluation/public/models.py
```

These dataclasses represent evaluation output inside services:

- `BenchmarkCase`
- `EvaluationMetric`
- `EvaluationCategory`
- `EvaluationCaseResult`
- `EvaluationRunSummary`
- `EvaluationRunDetail`

They keep evaluation scoring separate from HTTP response shape.

## API Schemas

File:

```text
app/backend/assessment_app/schemas/api.py
```

These are Pydantic models for HTTP request/response boundaries.

They are separate from domain dataclasses because API shapes and internal service shapes can change independently.

Key schemas:

- `IngestResponse`
- `AskRequest`
- `AskResponse`
- `SourceResponse`
- `AnalyticsResponse`
- `RunBenchmarkRequest`
- `EvaluationRunSummaryResponse`
- `EvaluationRunDetailResponse`
- `HealthResponse`

Routes use these schemas. Services do not need to know HTTP response shape.

## Interfaces

Folder:

```text
app/backend/assessment_app/interfaces/
```

Interfaces are Python `Protocol` contracts. They make services loosely coupled.

### `DocumentLoader`

File:

```text
interfaces/documents.py
```

Contract:

```text
load() -> list[DocumentBlock]
```

Current implementation:

```text
PdfDocumentLoader
```

Replaceable with:

- uploaded file loader
- S3 document loader
- HTML document loader

### `HierarchicalAwareParser`

File:

```text
services/rag/internal/ingestion/parser.py
```

Current implementation:

```text
HierarchicalAwareParser
```

Semantic chunking stays separate from parsing.

### `SemanticChunker`

File:

```text
services/rag/internal/ingestion/semantic_chunker.py
```

Current implementation:

```text
ContentBlock -> ChunkedContent[]
```

### `EmbeddingClient`

File:

```text
interfaces/embeddings.py
```

Contract:

```text
embed_documents(texts) -> list[list[float]]
embed_query(text) -> list[float]
```

Current implementation:

```text
OpenAICompatibleEmbeddingClient
```

Replaceable with:

- SentenceTransformers local client
- OpenAI SDK client
- HuggingFace client

### `VectorStore`

File:

```text
interfaces/vector_store.py
```

Contract:

```text
reset()
add_chunks(chunks, embeddings)
search(query_embedding, top_k)
count()
```

Current implementation:

```text
ChromaVectorStore
```

Replaceable with:

- FAISS
- Neo4j
- Pinecone
- Qdrant

### `ChatClient`

File:

```text
interfaces/chat.py
```

Contract:

```text
answer(messages) -> str
```

Current implementation:

```text
OpenAICompatibleChatClient
```

Replaceable with:

- Ollama-specific client
- OpenAI SDK client
- HuggingFace inference client

### `QueryLogger`

File:

```text
interfaces/logging.py
```

Contract:

```text
log_query(entry)
```

Current implementation:

```text
SqliteQueryLogger
```

Replaceable with:

- PostgreSQL logger
- SQLAlchemy repository
- event-stream logger

### `AnalyticsReader`

File:

```text
interfaces/analytics.py
```

Contract:

```text
total_queries()
answer_found_rate()
average_latency_ms()
frequent_questions(limit)
no_answer_queries(limit)
```

Current implementation:

```text
SqliteQueryLogger
```

The same concrete class implements query logging and analytics reading because both use the same SQLite table. Services still depend on interfaces.

## Infrastructure

Folder:

```text
app/backend/assessment_app/infra/
```

Infra contains concrete adapters for external systems.

### `PdfDocumentLoader`

File:

```text
infra/pdf_document_loader.py
```

Uses:

```text
pymupdf4llm
```

Flow:

```text
open PDF
-> read layout page boxes
-> ignore headers, footers, and pictures
-> return ordered DocumentBlock list
```

It does not chunk or embed. It only loads pages.

### `HierarchicalAwareParser`

File:

```text
services/rag/internal/ingestion/parser.py
```

Flow:

```text
read layout block text
-> detect numbered and indented bullet headings
-> preserve parent content, child section refs, and later parent content
-> resolve inline refs after all sections are known
-> return internal Section layout
```

Default:

```text
Stage 1 parser
```

Reason:

- keeps hierarchy and inline references explicit before chunking exists
- feeds semantic chunking and SQLite graph maps from a stable layout

### `OpenAICompatibleEmbeddingClient`

File:

```text
infra/openai_clients.py
```

Calls:

```text
POST {OPENAI_EMBEDDING_BASE_URL}/embeddings
```

Input:

```json
{"model": "...", "input": "..."}
```

Output:

```text
embedding vector
```

Used during:

- ingest for chunk embeddings
- ask for query embedding

### `OpenAICompatibleChatClient`

File:

```text
infra/openai_clients.py
```

Calls:

```text
POST {OPENAI_CHAT_BASE_URL}/chat/completions
```

Input:

```text
messages
model
temperature
max_tokens
```

Output:

```text
answer text
```

### `ChromaVectorStore`

File:

```text
infra/chroma_vector_store.py
```

Uses:

```text
chromadb.PersistentClient
```

Data path:

```text
app/backend/data/chroma
```

Main methods:

- `reset()` deletes and recreates collection
- `add_chunks()` stores chunk text, metadata, embeddings
- `search()` retrieves top-k source snippets
- `get_neighbors()` fetches chunks around matched chunk orders
- `get_section_chunks()` supports exact section lookup
- `get_referenced_sections()` follows stored section references
- `count()` checks whether ingest already happened

Why this adapter matters:

```text
RagQueryService does not know Chroma exists.
It only sees VectorStore.
```

### `SqliteQueryLogger`

File:

```text
infra/sqlite_query_logger.py
```

Uses:

```text
sqlite3
```

Data path:

```text
app/backend/data/usage.db
```

Creates table:

```sql
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_found INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    sources_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

Writes logs for every successful `/ask` service call.

Reads analytics:

- total queries
- answer-found rate
- average latency
- frequent questions
- no-answer queries

### `container.py`

File:

```text
infra/container.py
```

This is dependency wiring.

It builds:

- `RagQueryService`
- `AnalyticsService`
- `EvaluationService`

It decides concrete implementation:

```text
EmbeddingClient -> OpenAICompatibleEmbeddingClient
VectorStore -> ChromaVectorStore
QueryPlanner -> QueryPlanner
EvidenceService -> EvidenceService
ChatClient -> OpenAICompatibleChatClient
QueryLogger -> SqliteQueryLogger
AnalyticsReader -> SqliteQueryLogger
BenchmarkScorer -> DefaultBenchmarkScorer
EvaluationRunRepository -> SqliteEvaluationRepository
```

Why wiring is isolated:

```text
If Chroma changes to FAISS, container + infra change.
Services stay mostly untouched.
```

## Services

Folder:

```text
app/backend/assessment_app/services/
```

Services own business workflows.

### `DefaultIngestionParsingService`

File:

```text
services/rag/internal/ingestion/service_impl.py
```

Flow:

```text
load pages
-> parse hierarchical sections
-> return internal Section layout
```

It depends on:

- `DocumentLoader`
- `HierarchicalAwareParser`

It does not know:

- PDF implementation
- Chroma details
- HTTP routes
- env vars

### `RagQueryService`

File:

```text
services/rag_query_service.py
```

Flow:

```text
check vector store has chunks
-> plan original query plus retrieval branches
-> collect evidence with semantic search, exact section lookup, neighbors, and references
-> build grounded prompt
-> ask chat model
-> detect no-answer response
-> log query
-> return answer, sources, latency
```

It depends on:

- `VectorStore`
- `QueryPlanner`
- `EvidenceService`
- `ChatClient`
- `QueryLogger`

Important behavior:

```text
If no chunks exist, raises NotIngestedError.
If no sources come back, logs and returns standard no-answer message.
```

### `AnalyticsService`

File:

```text
services/analytics_service.py
```

Flow:

```text
read totals from AnalyticsReader
-> build dashboard summary dict
```

It depends on:

- `AnalyticsReader`

It does not query SQLite directly.

### `DefaultEvaluationService`

File:

```text
services/evaluation/internal/service_impl.py
```

Flow:

```text
receive benchmark run request
-> select static BenchmarkCase records
-> run QueryService.ask(log_query=false) for each case
-> score retrieval, answer, and system quality
-> persist run summary and case results
-> return benchmark run detail
```

Why `log_query=false` matters:

```text
evaluation is testing activity
normal analytics should describe real user ask traffic
```

### `DefaultBenchmarkScorer`

File:

```text
services/evaluation/internal/benchmark_scorer.py
```

Metric groups:

- Retrieval: section recall, section precision, evidence found, source count, dedupe rate.
- Answer: expected answer overlap, answer-found accuracy, citation section accuracy, unsupported-answer check.
- System: average latency, p95 latency, context volume, pass rate, total run latency.

Important limit:

```text
Expected Answer Overlap is lexical scoring, not a full factuality judge.
```

### `prompt_builder.py`

Builds the final messages sent to chat model.

Flow:

```text
source snippets
-> context block with [S1], [S2], section labels, page, chunk id, source type
-> system instruction
-> user question + context
```

### `QueryPlanner`

File:

```text
services/query_planner.py
```

Flow:

```text
clean question
-> keep original question as Q1
-> split multi-part questions into branches
-> detect exact Section X references
-> mark reference-heavy questions
```

### `EvidenceService`

File:

```text
services/evidence_service.py
```

Flow:

```text
for each retrieval query
-> embed query
-> semantic vector search
-> add exact section chunks
-> add neighbor chunks
-> add referenced sections when needed
-> dedupe and sort by document order
```

Important no-answer text:

```text
I could not find this in the AWS Customer Agreement.
```

`answer_found()` checks for this message in model output.

## Routes

Folder:

```text
app/backend/assessment_app/routes/
```

Routes are thin HTTP adapters.

They:

- receive request
- call service
- map service result to Pydantic response
- convert known errors to HTTP errors

They do not:

- parse PDF
- call Chroma
- write SQL
- call model APIs
- build prompts

### `GET /health`

File:

```text
routes/health.py
```

Returns:

```json
{"status": "ok"}
```

Used to check backend is alive.

### RAG Ingestion Rebuild

Stage 1 through Stage 4 rebuild configured PDF ingestion data through `POST /api/v1/ingest`. Current work lives under:

```text
services/rag/internal/ingestion/
```

Stage 4 stores embeddings only in the dedicated Chroma RAG collection and stores graph relationships in SQLite graph maps.

### `POST /ask`

File:

```text
routes/ask.py
```

Request:

```json
{
  "query": "What are customer responsibilities?",
  "top_k": 5
}
```

`top_k` is optional.

Calls:

```text
RagQueryService.ask()
```

Returns:

```json
{
  "answer": "...",
  "answer_found": true,
  "latency_ms": 1234,
  "sources": [
    {
      "chunk_id": "...",
      "text": "...",
      "page_start": 2,
      "page_end": 2,
      "source_file": "AWS Customer Agreement.pdf",
      "section_number": "2.1",
      "section_title": "Your Accounts",
      "source_type": "semantic",
      "score": 0.12
    }
  ]
}
```

### `GET /analytics`

File:

```text
routes/analytics.py
```

Calls:

```text
AnalyticsService.summary()
```

Returns:

```json
{
  "total_queries": 30,
  "answer_found_rate": 0.8,
  "average_latency_ms": 1200,
  "frequent_questions": [],
  "no_answer_queries": []
}
```

### `POST /evaluation/runs`

File:

```text
routes/evaluation_routes.py
```

Request:

```json
{
  "top_k": 5,
  "case_ids": null
}
```

Calls:

```text
EvaluationService.run_benchmark()
```

Returns:

```json
{
  "summary": {
    "run_id": "eval_...",
    "overall_score": 0.86,
    "retrieval_score": 0.84,
    "answer_score": 0.88,
    "system_score": 0.86
  },
  "categories": [],
  "cases": []
}
```

### Error Mapping

File:

```text
routes/errors.py
```

Known service errors become HTTP errors.

Example:

```text
NotIngestedError -> HTTP 409
```

Unknown errors become:

```text
HTTP 500
```

## Full Backend Flow

### Ingest Flow

Endpoint:

```text
DefaultIngestionParsingService.parse()
-> loader returns DocumentBlock list
-> HierarchicalAwareParser.parse()
-> parser returns internal Section layout
-> DefaultSemanticChunkingService.chunk()
-> semantic chunks get cached embeddings
```

### Ask Flow

Endpoint:

```text
POST /ask
```

Detailed flow:

```text
route validates AskRequest
-> FastAPI dependency creates RagQueryService
-> service checks vector store count
-> service builds query plan
-> evidence service runs semantic search
-> evidence service expands exact sections, neighbors, and references
-> service builds prompt from retrieved snippets
-> service asks chat model
-> service marks answer_found true/false
-> service writes SQLite log row
-> route maps result to AskResponse
```

### Analytics Flow

Endpoint:

```text
GET /analytics
```

Detailed flow:

```text
route creates AnalyticsService
-> service asks AnalyticsReader for metrics
-> SqliteQueryLogger runs SQL queries
-> service returns summary dict
-> route maps to AnalyticsResponse
```

### Evaluation Flow

Endpoint:

```text
POST /evaluation/runs
```

Detailed flow:

```text
route validates RunBenchmarkRequest
-> FastAPI dependency provides EvaluationService
-> service loads static BenchmarkCase dataset
-> service calls QueryService.ask(log_query=false) for each case
-> query service runs normal planning, evidence, prompt, and model flow
-> benchmark scorer scores retrieval, answer, and system quality
-> SQLite repository stores run summary and per-case results
-> route maps run detail to EvaluationRunDetailResponse
```

## Frontend Layout

```text
app/frontend/
  package.json
  index.html
  src/
    api.js
    evaluation/
    main.jsx
    styles.css
```

## Frontend Flow

### `api.js`

Central place for HTTP calls.

Functions:

- `ingestDocument()`
- `askQuestion(query)`
- `loadAnalytics()`
- `runEvaluation(topK)`
- `loadEvaluationRuns()`
- `loadEvaluationRun(runId)`

Uses:

```text
VITE_API_BASE_URL
```

Default:

```text
http://localhost:8000
```

### `main.jsx`

Owns UI state.

State:

- active tab: chat, analytics, or evaluation
- question input
- latest answer
- analytics payload
- status/errors
- loading flag

Chat tab:

```text
question input
-> Ask button
-> answer card
-> source cards
```

Analytics tab:

```text
total queries
answer rate
average latency
frequent questions table
no-answer queries table
```

Evaluation tab:

```text
query input
-> top-k input
-> Run button
-> overall score band
-> evidence, optimization, performance metric cards
-> answer and evidence sources
```

Ingest controls are paused while the RAG ingestion pipeline is rebuilt.

### `styles.css`

Simple dashboard styling:

- restrained app shell
- tabs
- chat form
- source cards
- analytics cards
- evaluation score cards
- responsive mobile layout

No business logic here.

## Runtime Data

Ignored paths:

```text
app/backend/data/
app/frontend/node_modules/
app/frontend/dist/
```

Why:

- Chroma persistence is generated runtime data
- SQLite database is generated runtime data
- frontend dependencies/build artifacts are generated

## Testing

Backend tests:

```text
app/backend/tests/integration/infra/test_chroma_vector_store.py
app/backend/tests/integration/infra/test_pdf_document_loader.py
app/backend/tests/integration/infra/test_sqlite_query_logger.py
app/backend/tests/unit/internal/test_evidence_collector.py
app/backend/tests/unit/internal/test_query_planner.py
app/backend/tests/unit/services/test_hierarchical_parser.py
app/backend/tests/unit/services/test_semantic_chunking.py
```

Current tests cover:

- section-aware chunk metadata, neighbors, and references
- query planning for multi-part and section-targeted questions
- evidence expansion and dedupe flow
- evaluation metric grouping
- evaluation service uses real query flow without logging to analytics
- Chroma graph-evidence methods
- SQLite logging and analytics queries

Run:

```bash
cd app/backend
pytest
```

Frontend build check:

```bash
cd app/frontend
npm run build
```

## How To Extend

### Replace Chroma With FAISS

Add:

```text
infra/faiss_vector_store.py
```

Implement:

```text
VectorStore
```

Change wiring in:

```text
infra/container.py
```

Services unchanged.

### Replace OpenAI-Compatible Chat

Add:

```text
infra/ollama_chat_client.py
```

Implement:

```text
ChatClient
```

Change wiring in:

```text
infra/container.py
```

Routes and services unchanged.

### Add Semantic Chunking

Add:

```text
services/rag/internal/ingestion/semantic_chunker.py
services/rag/internal/ingestion/graph_builder.py
infra/sqlite/sqlite_graph_store.py
```

Implement:

```text
semantic chunking stage
SQLite graph-map stage
```

Keep parsing, semantic chunking, graph maps, and persistence separate.

Change wiring in:

```text
infra/container.py
```

Ingest service unchanged.

### Move SQLite To PostgreSQL

Add:

```text
infra/postgres_query_logger.py
```

Implement:

```text
QueryLogger
AnalyticsReader
```

Change wiring in:

```text
infra/container.py
```

Query and analytics services unchanged.

## What To Explain In A Walkthrough

Short version:

```text
The app follows ports-and-adapters style. Routes are thin HTTP adapters. Services own use cases. Interfaces define what services need. Infra supplies replaceable implementations. This keeps the RAG pipeline easy to read and easy to swap.
```

Backend walkthrough:

1. Start at `main.py`.
2. Show routes.
3. Show `services/rag/internal/ingestion/` and `RagQueryService`.
4. Show interfaces each service depends on.
5. Show infra implementations.
6. Show SQLite analytics.
7. Show benchmark evaluation flow and why it avoids analytics logging.

Frontend walkthrough:

1. Show `api.js` talks to FastAPI.
2. Show `main.jsx` has chat, analytics, and evaluation tabs.
3. Show source snippets are displayed under answers.
4. Show `src/evaluation/EvaluationView.jsx` owns evaluation UI.

Assessment walkthrough:

1. Run backend.
2. Run frontend.
3. Click Ingest.
4. Ask answerable question.
5. Ask out-of-scope question.
6. Open analytics tab.
7. Show SQL-backed stats.
8. Open evaluation tab.
9. Run the benchmark evaluation and inspect failed cases.

## Current Limits

This is a clean assessment app, not full production.

Known limits:

- one static source PDF
- no user auth
- no file upload UI
- no streaming answer
- no reranking
- no multi-document filtering
- no deployment config yet
- no LLM-as-judge evaluation yet
- no token-cost evaluation yet
- no CI benchmark gate yet

The codebase is structured so these can be added without rewriting core services.
