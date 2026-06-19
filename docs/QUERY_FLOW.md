# RAG Query Flow Explained

This document outlines the 5 detailed stages of our Self-Reflective (Agentic) Query pipeline, demonstrating the problems solved, the data structures used, and providing mapped examples for each phase.

---

## Stage 1: Agentic Query Planning

### The Problem
Users frequently ask multi-part, conversational questions like "What are my obligations and what happens if I breach them?" 
Dense embedding models struggle with this because a single vector cannot simultaneously represent two completely different concepts accurately. We need to split the intent before searching.

### Quick Example
```text
User Query: "What is the SLA uptime and how do I report a breach?"

Plan:
  - Query 1: "SLA uptime percentage definition"
  - Query 2: "reporting a breach process"
```
Notice: One complex query becomes two highly targeted keyword searches.

### The Data Structure
```typescript
type QueryPlan = {
  originalQuery: string;
  retrievalQueries: RetrievalQuery[];
};

type RetrievalQuery = {
  queryId: string;
  query: string;
  purpose: string;
  targetSections: string[];
  includeReferences: boolean;
};
```

### Mapped Example
```json
{
  "originalQuery": "What is the SLA uptime and how do I report a breach?",
  "retrievalQueries": [
    {
      "queryId": "Q1",
      "query": "SLA uptime percentage definition",
      "purpose": "Find the service level agreement metrics",
      "targetSections": [],
      "includeReferences": false
    },
    {
      "queryId": "Q2",
      "query": "reporting a breach process",
      "purpose": "Find the procedure for notifying the provider",
      "targetSections": [],
      "includeReferences": false
    }
  ]
}
```

### Key Points
- An LLM acts as a router, returning strict JSON to break down the query.
- If the user explicitly mentions "Section 4.1", it is extracted into `targetSections` to completely bypass vector search and perform an exact graph lookup.
- **What is not tackled:** Caching. Every identical user query re-runs the planning LLM call.

---

## Stage 2: Initial Evidence Collection

### The Problem
Before we can evaluate context, we need a baseline of potentially relevant chunks. Relying purely on semantic vector search can miss exact clauses when user wording differs from contract wording. For example, "promise about securing customer content" may rank the Section 8 disclaimer above Section 1.3 unless we add lexical and legal-phrase signals.

### Quick Example
User Query: "According to Section 2.1, what is the fee?"
Action: 
1. Extract explicit section references from the original and planned query.
2. Expand contract-language synonyms before retrieval.
3. Run semantic vector search and SQLite lexical search.
4. Merge exact-section, lexical, and vector candidates.
5. Rerank to the final evidence budget.

### The Data Structure
```typescript
type SourceSnippet = {
  chunkId: string;
  text: string;
  sectionId: string;
  sectionTitle: string;
  order: number;
  sourceType: "semantic" | "exact_section" | "parent" | "neighbor" | "reference";
};
```

### Mapped Example
```json
[
  {
    "chunkId": "chunk_45",
    "text": "1. A 5% penalty applies.",
    "sectionId": "section_2_1",
    "sectionTitle": "Section 2.1",
    "order": 45,
    "sourceType": "exact_section"
  },
  {
    "chunkId": "chunk_102",
    "text": "Late fees are calculated monthly.",
    "sectionId": "section_8",
    "sectionTitle": "General Billing",
    "order": 102,
    "sourceType": "semantic"
  }
]
```

### Key Points
- The collector queries ChromaDB for semantic hits and SQLite for exact graph and lexical hits.
- LLM-planned `targetSections` are treated as hints. They are fetched only if explicit or validated by title/text overlap.
- The reranker boosts direct section/title/phrase matches and demotes front matter or indirect disclaimer evidence.
- Fixed failure classes include Section 8 beating Section 1.3, Section 1.4/6.4 beating Section 6.1, and agreement boilerplate beating Section 5.1.

---

## Stage 3: Self-Reflective Verification & Context Expansion

### The Problem
Standard RAG blindly grabs the initial chunks and feeds them to the generator. Often, a retrieved chunk is a sub-bullet point ("The fee is 5%"). The LLM has no idea *what* the fee is for because the parent section title wasn't retrieved. We need to verify context and deterministically fetch missing pieces.

### Quick Example
```text
Retrieved Evidence: "1. A 5% penalty applies."
User Query: "What happens if I pay late?"
```
*Verifier Evaluation:* Evidence lacks parent context.
*Action:* SQLite GraphMap queried for `chunk_45`'s parent. Appends parent chunk to evidence pool.

### The Data Structure
```typescript
type VerificationResult = {
  isSufficient: boolean;
  needsReferences: boolean;
  needsParents: boolean;
  needsChildren: boolean;
  needsNeighbors: boolean;
  issues: string[];
};
```

### Mapped Example
```json
{
  "isSufficient": false,
  "needsReferences": false,
  "needsParents": true,
  "needsChildren": false,
  "needsNeighbors": false,
  "issues": [
    "The chunk mentions a penalty but does not define the condition (late payment) that triggers it."
  ]
}
```

### Key Points
- A lightweight LLM judge returns strict boolean flags directing the system on *how* to expand the graph (`needsParents`, `needsNeighbors`).
- The SQLite edges (`parentSectionId`, `nextChunkId`) are queried instantly to fetch exactly what surrounded the retrieved text in the original document.
- This creates a `while` loop (capped at a max retry limit) until `isSufficient: true`.
- Verifier failures fail closed. If JSON parsing or model calls fail, evidence is treated as insufficient rather than accepted.
- **What is not tackled:** Infinite semantic drift. We strictly limit expansion hops.

---

## Stage 4: Final Grounded Generation

### The Problem
Once we have perfect evidence, the LLM might still hallucinate external knowledge or fail to cite the sources properly.

### Quick Example
We provide the verified chunks to the LLM and strictly instruct it: "Answer ONLY using the provided evidence. If the answer is not present, reply with 'No answer found'."

### The Data Structure
```typescript
type AskResult = {
  answer: string;
  answerFound: boolean;
  sources: SourceSnippet[];
  latencyMs: number;
};
```

### Mapped Example
```json
{
  "answer": "If you pay late, a 5% penalty applies to the invoice.",
  "answerFound": true,
  "sources": [
    {
      "chunkId": "chunk_45",
      "text": "1. A 5% penalty applies.",
      "sectionId": "section_late_fees",
      "sectionTitle": "Late Fees",
      "order": 45,
      "sourceType": "semantic"
    }
  ],
  "latencyMs": 4200
}
```

### Key Points
- The prompt enforces strict grounding.
- The answer prompt requires direct evidence. Related but indirect evidence must produce the standard no-answer message.
- The `AskResult` returns the exact sources used, so the frontend UI can build clickable citations.
- `AskResult.trace` optionally returns planned queries, candidate pools, reranked candidates, verifier decisions, and expansion actions for debugging.

---

## Stage 5: Analytics Logging

### The Problem
We need to measure system usage, latency, and hallucination metrics over time to populate the `GET /analytics` dashboard, without blocking the user's HTTP response unnecessarily.

### Quick Example
After generation, the orchestration service serializes the `AskResult` and executes a fast SQLite `INSERT`.

### The Data Structure
```sql
CREATE TABLE query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_found BOOLEAN NOT NULL,
    latency_ms INTEGER NOT NULL,
    sources_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Mapped Example
```json
[
  {
    "id": 1,
    "query": "What happens if I pay late?",
    "answer": "If you pay late, a 5% penalty applies to the invoice.",
    "answer_found": true,
    "latency_ms": 4200,
    "sources_json": "[{...}]",
    "created_at": "2026-06-18 10:00:00"
  }
]
```

### Key Points
- A single denormalized table provides fast `GROUP BY`, `COUNT`, and `AVG` for the analytics dashboard.
- Logging occurs at the very end of the orchestration.
- **What is not tackled:** Dedicated asynchronous message queues. The logging happens inline before returning the HTTP response, which adds slight latency.
