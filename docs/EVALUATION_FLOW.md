# Benchmark Evaluation Flow Explained

This document outlines the detailed stages of our Benchmark Evaluation pipeline, demonstrating how we measure and track the RAG system's accuracy over time without polluting normal analytics.

---

## Stage 1: Deterministic Benchmark Execution

### The Problem
Normal product analytics are skewed by test queries. We need a way to run a comprehensive, stable suite of queries against the RAG system to measure regressions, without adding test traffic to the `query_logs` table that powers the dashboard.

### Quick Example
```text
Action: Run the 30-case "AWS Customer Agreement" benchmark dataset.
Process: The system calls the exact same `QueryService.ask()` used by the API, but with a special `log_query=false` flag.
```

### The Data Structure
```typescript
type BenchmarkCase = {
  caseId: string;
  query: string;
  expectedAnswer: string;
  expectedSections: string[];
  answerable: boolean;
  tags: string[];
};
```

### Mapped Example
```json
{
  "caseId": "case_payment_01",
  "query": "What happens if I don't pay?",
  "expectedAnswer": "A 1.5% late fee applies per month.",
  "expectedSections": ["section_2_payment"],
  "answerable": true,
  "tags": ["payment", "direct_clause"]
}
```

### Key Points
- The benchmark cases are hardcoded against a stable source document, ensuring stable longitudinal tracking.
- Coverage includes unanswerable checks to verify the system strictly refuses hallucination.
- **What is not tackled:** Dynamic dataset generation via LLMs. The dataset is currently manually curated for maximum ground-truth accuracy.

---

## Stage 2: Objective Scoring Engine

### The Problem
After the `QueryService` returns an answer and the sources it used, we need an objective, deterministic way to calculate if the retrieval was accurate (Precision/Recall) and if the answer was correct, without manually reading 30 outputs.

### Quick Example
```text
System Output: Answered "1.5% fee" using `chunk_45` from `section_2_payment`.
Scorer: Matches `section_2_payment` against `expectedSections`. Yields Section Recall = 1.0.
```

### The Data Structure
```typescript
type CaseResult = {
  caseId: string;
  passed: boolean;
  actualAnswer: string;
  retrievedSections: string[];
  metrics: {
    sectionRecall: number;
    sectionPrecision: number;
    expectedAnswerOverlap: number;
    answerFoundAccuracy: number;
    citationSectionAccuracy: number;
    unsupportedAnswerPenalty: number;
  };
  latencyMs: number;
  sourcesJson: string;
};
```

### Mapped Example
```json
{
  "caseId": "case_payment_01",
  "passed": true,
  "actualAnswer": "Late invoices incur a 1.5% penalty per month.",
  "retrievedSections": ["section_2_payment", "section_4_taxes"],
  "metrics": {
    "sectionRecall": 1.0,
    "sectionPrecision": 0.5,
    "expectedAnswerOverlap": 0.85,
    "answerFoundAccuracy": 1.0,
    "citationSectionAccuracy": 1.0,
    "unsupportedAnswerPenalty": 0.0
  },
  "latencyMs": 3200,
  "sourcesJson": "[...]"
}
```

### Key Points
- `Section Recall` measures if we found the gold context. `Section Precision` measures how much noise we retrieved.
- `Unsupported Answer Penalty` heavily punishes the system if it returns an answer but failed to retrieve the required sections (identifying hallucinations).
- **What is not tackled:** LLM-as-a-judge factuality scoring. Currently, the scoring is deterministic and lexical (Overlap).

---

## Stage 3: Evaluation Persistence & History

### The Problem
A single run tells us how we did today, but we need to track regressions across code changes, top-k adjustments, or model swaps.

### Quick Example
```text
Run 1 (top_k=3): Score 75%
Run 2 (top_k=5): Score 92%
```

### The Data Structure
**API Response Schema:**
```typescript
type RunSummary = {
  runId: string;
  configSnapshot: string;
  totalCases: number;
  passRate: number;
  avgSectionRecall: number;
  avgExpectedAnswerOverlap: number;
  avgLatencyMs: number;
  createdAt: string;
};
```

### Mapped Example
```json
{
  "runId": "run_982bca",
  "configSnapshot": "chat=gpt-4o-mini; embedding=nomic-embed-text; top_k_default=5",
  "totalCases": 30,
  "passRate": 0.96,
  "avgSectionRecall": 0.98,
  "avgExpectedAnswerOverlap": 0.88,
  "avgLatencyMs": 4100,
  "createdAt": "2026-06-18 10:00:00"
}
```

### Key Points
- Results are stored in dedicated SQLite tables (`evaluation_runs` and `evaluation_case_results`).
- The `configSnapshot` permanently binds the LLM string configurations to the result, making model comparisons completely trivial.
- **What is not tackled:** Cost estimation tracking. Dollar cost per benchmark run is not currently tracked.
