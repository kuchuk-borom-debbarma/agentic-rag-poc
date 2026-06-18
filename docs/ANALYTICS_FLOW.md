# Analytics & Logging Flow Explained

This document outlines the tracking and analytics pipeline of the application, detailing how we safely capture RAG usage metrics and expose them via SQL aggregation as per the assessment requirements.

---

## Stage 1: Pipeline Orchestration Logging

### The Problem
We need to record every single interaction with the question-answering endpoint (including the exact sources used and whether the LLM hallucinated) to evaluate the RAG system's real-world performance. However, we cannot let the logging mechanism complicate the core LLM orchestration logic or require heavy external database containers.

### Quick Example
```text
User asks: "What happens if I breach the SLA?"
LLM Generator replies: "No answer found in context."
```
*Action:* The orchestrator calculates that this took 1,200ms and flags `answer_found = 0`. It instantly writes this to a local SQLite file before returning the HTTP response.

### The Data Structure
**Python Domain Model:**
```typescript
type QueryLogEntry = {
  query: string;
  answer: string;
  answerFound: boolean;
  latencyMs: number;
  sourcesJson: string; // Serialized array of SourceSnippet objects
};
```

**SQLite Schema:**
```sql
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_found INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    sources_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Mapped Example
```json
{
  "id": 42,
  "query": "What happens if I breach the SLA?",
  "answer": "No answer found in context.",
  "answer_found": 0,
  "latency_ms": 1200,
  "sources_json": "[]",
  "created_at": "2026-06-18 14:32:01"
}
```

### Key Points
- SQLite is utilized as the persistent storage layer because it is serverless, zero-configuration, and extremely fast for local inserts, perfectly fulfilling the assessment constraints.
- We deliberately track `answer_found` as an integer boolean. Our strict LLM prompts prevent hallucinations by forcing a "No answer found" reply when evidence is lacking. Tracking this allows us to directly measure the system's "hallucination prevention" rate.
- **What is not tackled:** Asynchronous Message Queues. The `INSERT` statement happens synchronously at the end of the `/ask` route. For massive scale, this would be pushed to an event stream (e.g., Kafka or Redis) to avoid adding even a few milliseconds to the user's HTTP request.

---

## Stage 2: SQL-Backed Metrics Aggregation

### The Problem
The assessment explicitly requires exposing metrics like "Most frequently asked questions" and "Average response latency" backed by SQL (`GROUP BY`, `COUNT`, `AVG`). We need a clean API boundary that converts raw SQL aggregates into a strictly typed JSON dashboard payload.

### Quick Example
The React dashboard needs to know the top questions asked. The backend runs a `GROUP BY` query and returns the structured data.

### The Data Structure
**API Response Schema:**
```typescript
type AnalyticsResponse = {
  totalQueries: number;
  answerFoundRate: number; // e.g., 0.85 (85%)
  averageLatencyMs: number;
  frequentQuestions: Array<{ query: string; count: number }>;
  noAnswerQueries: Array<{ query: string; created_at: string }>;
};
```

### Mapped Example
**SQL Executed:**
```sql
-- Most Frequently Asked Questions
SELECT query, COUNT(*) AS count 
FROM query_logs 
GROUP BY query 
ORDER BY count DESC, query ASC 
LIMIT 10;

-- Queries where no answer was found
SELECT query, created_at 
FROM query_logs 
WHERE answer_found = 0 
ORDER BY created_at DESC 
LIMIT 10;
```

**JSON Output (`GET /api/v1/analytics`):**
```json
{
  "totalQueries": 145,
  "answerFoundRate": 0.92,
  "averageLatencyMs": 3150.5,
  "frequentQuestions": [
    {
      "query": "What are the payment terms?",
      "count": 12
    }
  ],
  "noAnswerQueries": [
    {
      "query": "Does the SLA cover AWS Outposts?",
      "created_at": "2026-06-18 14:32:01"
    }
  ]
}
```

### Key Points
- The `/analytics` endpoint acts purely as a read-model. The `SqliteQueryLogger` port simply fetches pre-aggregated rows directly from the SQLite engine.
- Offloading the aggregation to SQLite (`AVG()`, `COUNT()`) is significantly faster and uses less memory than pulling all rows into Python and calculating the metrics manually.
- **What is not tackled:** Time-series filtering. The current endpoint aggregates *all* time data. It does not support filtering by `?start_date=` or `?end_date=`, which would be required for a production dashboard.
