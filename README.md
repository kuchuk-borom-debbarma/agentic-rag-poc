# Junior AI Developer Assignment - RAG Assessment

This repository contains a complete Retrieval-Augmented Generation (RAG) system for querying the AWS Customer Agreement, built as part of the Junior AI Developer Assignment. 

## Project Layout

- **`app/`**: The final deliverable. A clean, interface-first React + FastAPI application with SQLite-backed usage logging, benchmark evaluation history, and ChromaDB vector storage.
- **`experimental-prototype/`**: An experimental, Neo4j and LangGraph-based ingestion pipeline from earlier proof-of-concept work.

**All instructions below apply to the `app/` directory**, which is the final assessment submission.

---

## 1. Setup and Run Instructions

The application consists of a FastAPI backend and a React/Vite frontend.

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend Setup

Navigate to the backend directory:
```bash
cd app/backend
```

1. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
cp .env.example .env
```
*(See **Model Configuration** below to set up your LLM and Embedding API keys in the `.env` file.)*

3. Start the FastAPI server:
```bash
uvicorn assessment_app.main:app --reload
```
The API will run at `http://localhost:8000`.

### Frontend Setup

Navigate to the frontend directory:
```bash
cd app/frontend
```

1. Install dependencies:
```bash
npm install
```

2. Configure environment variables:
```bash
cp .env.example .env
```

3. Start the React development server:
```bash
npm run dev
```
The UI will run at `http://localhost:5173`.

---

## 2. Model Configuration

The system uses OpenAI-compatible HTTP endpoints, allowing maximum flexibility (you can use OpenAI, local Ollama, or HuggingFace endpoints).

Configure your preferred providers in `app/backend/.env`:

```env
# Example using local Ollama for embeddings
OPENAI_EMBEDDING_BASE_URL=http://localhost:11434/v1
OPENAI_EMBEDDING_MODEL=nomic-embed-text
OPENAI_EMBEDDING_API_KEY=local

# Example using OpenAI for chat completion
OPENAI_CHAT_BASE_URL=https://api.openai.com/v1
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_CHAT_API_KEY=your-api-key
```

---

## 3. Architecture Overview

The system follows a strict **Interface-First / Dependency Inversion** architecture to keep business logic agnostic of the infrastructure (e.g., swapping ChromaDB for FAISS without rewriting the services).

> [!NOTE]
> For a detailed, step-by-step technical breakdown of the internal pipelines (including data structures, problem statements, and visual examples), please see:
> - **[Ingestion Flow Deep Dive](docs/INGESTION_FLOW.md)**
> - **[Query Flow Deep Dive](docs/QUERY_FLOW.md)**
> - **[Analytics & Logging Deep Dive](docs/ANALYTICS_FLOW.md)**
> - **[Evaluation Flow Deep Dive](docs/EVALUATION_FLOW.md)**

```text
React Frontend (Vite + Tailwind)
  -> FastAPI Backend
      -> Routing Layer (HTTP Request/Response boundaries)
      -> Service Layer (Business Logic)
          -> RAG Ingestion Service: Parses PDF, extracts hierarchy, chunks semantically, embeds.
          -> RAG Query Service: Plans queries, retrieves vectors, expands evidence, queries LLM.
          -> Analytics Service: Reads SQLite usage aggregates.
          -> Evaluation Service: Runs benchmark cases without analytics logging to measure retrieval, answer, and system quality.
      -> Interface Layer (Protocols: VectorStore, DocumentLoader, ChatClient)
      -> Infrastructure Layer (Concrete Adapters: ChromaVectorStore, PdfDocumentLoader, SqliteQueryLogger)
```

**Data Flow:**
1. **POST `/api/v1/ingest`**: Rebuilds the PDF into graph maps and stores vectors in a ChromaDB collection.
2. **POST `/api/v1/ask`**: Plans retrieval, fetches semantic matches, expands evidence with neighboring chunks and references, prompts the chat model, returns the answer, and logs the interaction to SQLite.
3. **GET `/api/v1/analytics`**: Aggregates usage metrics from the SQLite database.

---

## 4. Key Design Decisions & Assumptions

### Chunking Strategy & Parsing
- **Decision:** A custom `HierarchicalAwareParser` coupled with semantic chunking.
- **Reasoning:** Rather than simple fixed-length chunking which destroys document context, the system first detects headings, lists, and sections to build a structured hierarchy. It then semantically chunks the content while preserving parent headers, section numbers, and inline references. This means chunks carry their semantic context natively, reducing hallucination and improving targeted retrieval.

### Retrieval Relevance & `top_k`
- **Decision:** Default `top_k` is 5, augmented with **Evidence Expansion**.
- **Reasoning:** 5 chunks provide sufficient evidence for direct questions without blowing up the LLM's context window. However, to guarantee completeness, the system actively expands retrieved evidence by fetching `DEFAULT_NEIGHBORS=1` (the chunk immediately before and after the match) and exact section lookups if the user mentions a specific section (e.g., "Section 1.2").

### Model / Provider Choice
- **Decision:** Agnostic LLM clients via LangChain LCEL and Pydantic Output Parsers.
- **Reasoning:** Rather than hardcoding native API clients or brittle string-parsing, the backend uses LangChain's `ChatOpenAI` and `OpenAIEmbeddings` interfaces. This allows swapping between paid APIs (OpenAI), free-tier remote APIs (HuggingFace Inference), and local models (Ollama) entirely via environment variables. `PydanticOutputParser` guarantees strict structural JSON compliance from the LLM (crucial for our Agentic Routing and Verification loops) across any compatible provider.

### Analytics Logging & SQL Schema
- **Decision:** SQLite with a single denormalized `query_logs` table.
- **Reasoning:** For a lightweight analytics dashboard, SQLite avoids the need to run an external PostgreSQL container. The `query_logs` table captures the `query`, `answer`, `answer_found` flag, `latency_ms`, `timestamp`, and JSON `sources_json`. This enables efficient `GROUP BY`, `COUNT`, and `AVG` aggregations for the `/analytics` endpoint.

---

## 5. Demo & Verification

### Running the Seed Queries
To populate the analytics dashboard with realistic data, run the seed queries script after the app is up and the document is ingested:

```bash
cd app/backend
python scripts/seed_queries.py
```
This script will execute 30+ mixed test queries (both answerable and irrelevant) to simulate real traffic, fulfilling the assessment requirement.

### Code Quality Verification
Backend tests:
```bash
pip install -r requirements-dev.txt
pytest
```
Syntax validation:
```bash
python -m compileall assessment_app
```
