# Agentic RAG Proof of Concept

This repository contains a complete, deterministically evaluated Retrieval-Augmented Generation (RAG) system for querying the AWS Customer Agreement. 

The application consists of a FastAPI backend and a React/Vite frontend. All core source code is located within the **`app/`** directory.

---

## 🌟 Benchmark Highlights
The system is deterministically evaluated against a strict 30-case benchmark suite to penalize hallucinations. During the latest evaluation (`gemini-3.1-flash-lite` + `qwen3-embedding`):
- **90.0% Pass Rate:** Successfully answered or safely rejected 27 out of 30 complex legal questions.
- **93.3% Hallucination Safety:** Actively recognized and rejected unanswerable "trap" questions without generating false claims.
- **74.1% Section Recall:** Successfully traversed the SQLite document graph to locate the precise, expected legal clauses.

---

## 📚 Documentation & Deep Dives

To keep this README clean, all technical overviews, architecture decisions, and benchmark data have been organized into standalone documents. Please review them here:

**Core Reports:**
- 📄 **[Technical Report](TECHNICAL_REPORT.md)** - A comprehensive 3-page overview of the entire system architecture, answering *why* this system minimizes hallucinations.
- 📊 **[Evaluation Report](EVALUATION_REPORT.md)** - Detailed analysis of the mathematical benchmarking, section recall, and latency.
- 🗄️ **[Raw Benchmark CSV Data](app/evaluation/benchmark_results.csv)** - The raw 30-case SQLite data export for independent analysis.

**Internal Pipeline Deep Dives:**
- ⚙️ [Ingestion Flow](docs/INGESTION_FLOW.md)
- 🧠 [Query Flow](docs/QUERY_FLOW.md)
- 📈 [Analytics Logging Flow](docs/ANALYTICS_FLOW.md)
- ⚖️ [Evaluation Flow](docs/EVALUATION_FLOW.md)

*(Note: The `experimental-prototype/` folder contains exploratory Proof-of-Concept testing logic and is fully explained in its own README).*

---

## 🚀 Setup and Run Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+

### Quick Start (The Fast Way)
If you already have Python and Node installed, the easiest way to run the full stack is using the root start script:
```bash
./start.sh
```
This script will concurrently boot up both the FastAPI backend and the React frontend. It will also gracefully shut them down if you hit `Ctrl+C`.

**Once the servers are running, everything can be done straight from the React Web UI (`http://localhost:5173`):**
- **Query View:** Ask questions and watch the Agentic Verification loop work.
- **Analytics View:** Inspect your usage logs and system latencies.
- **Evaluation View:** Review the deterministic benchmark scoring.

---

### Manual Setup (The Detailed Way)

**1. Backend Setup**
Navigate to the backend directory:
```bash
cd app/backend
```

Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure environment variables:
```bash
cp .env.example .env
```
*(Open `.env` and insert your OpenAI, HuggingFace, or local Ollama endpoints).*

Start the FastAPI server:
```bash
uvicorn assessment_app.main:app --reload
```
The API will run at `http://localhost:8000`.

**2. Frontend Setup**
Navigate to the frontend directory:
```bash
cd app/frontend
```

Install dependencies and start the React development server:
```bash
npm install
npm run dev
```
The UI will run at `http://localhost:5173`.

### 3. Data Ingestion (Using the PDF)
The target AWS document is pre-packaged in the repository at: **`app/resources/AWS Customer Agreement.pdf`**.
Once both servers are running, navigate to the frontend UI (`http://localhost:5173`) and click the **"Ingest Document"** button. The backend will automatically read the PDF, build the SQLite relational graph, and store the embeddings in ChromaDB.

---

## 🧪 Demo & Verification

### Running the Seed Queries
To populate the analytics dashboard with realistic data, run the seed queries script after the app is up and the document is ingested:

```bash
cd app/backend
python scripts/seed_queries.py
```
This script executes 30+ mixed test queries (both answerable and irrelevant) to simulate real traffic.

### Code Quality Verification
Run the backend tests:
```bash
cd app/backend
pip install -r requirements-dev.txt
pytest
```
Validate python syntax:
```bash
python -m compileall assessment_app
```
