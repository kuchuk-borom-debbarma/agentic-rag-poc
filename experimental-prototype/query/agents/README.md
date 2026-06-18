# Query Agents

This folder contains an advanced, highly defensive **Agentic RAG** testing loop with strict grounding and an iterative feedback system.

## Architectural Flow

The pipeline is designed to eliminate hallucination through structural auditing and iterative self-correction:

```text
User Question
  -> RouterAgent
      -> Decomposes complex questions into parallel retrieval sub-queries.
      -> Outputs explicit search intents while preserving the original question.
      
[ ITERATIVE RETRIEVAL LOOP START ]
  -> SemanticSearchAgent
      -> Executes vector searches for each active sub-query against the Neo4j Graph.
  -> EvidenceAgent
      -> Aggregates hits and merges/dedupes graph chunks.
  -> Subanswer stage (AnswerAgent)
      -> Attempts to answer each sub-query strictly using ONLY the retrieved context.
  -> VerifierAgent
      -> Audits each subanswer mathematically against the retrieved chunks. Marks valid/invalid.
  -> FinalAnswer stage (AnswerAgent)
      -> Synthesizes the final answer using only verified subanswers.
  -> FinalVerifier stage (VerifierAgent)
      -> Performs a final safety audit of the synthesized answer.

  -> Decision Point:
      -> If Valid = True: Return answer to user.
      -> If Valid = False:
          -> ReflectionAgent
              -> Reads the exact failure reasons (e.g., "missing definition of X").
              -> Generates NEW, highly targeted search queries.
              -> Modifies retrieval parameters (e.g., expanding graph neighbors or linked references).
              -> Loops back to SemanticSearchAgent for Pass 2.
[ ITERATIVE RETRIEVAL LOOP END ]
```

## Core Design Principles

1. **Strict Grounding:** The `AnswerAgent` and `VerifierAgent` are strictly prompted to rely *only* on the provided context. If a question cannot be answered by the document, the system explicitly states the missing information and rejects the answer rather than guessing.
2. **Dynamic Context Footprint:** By default, the system runs with `neighbors=0` (exact chunk matching). The context is only expanded via the `ReflectionAgent` if the initial precise search fails to provide enough information.
3. **Graph-Aware Retrieval:** The `EvidenceAgent` can walk the Neo4j graph to fetch cross-referenced sections when the LLM determines that explicit legal/technical links are required.

## Technical Assumptions & Production Trade-Offs

Given the 48-hour time limit for this assessment, the functional logic (Semantic Routing, Verifiers, and Reflection loops) is built to state-of-the-art standards. However, the engineering execution makes a few intentional trade-offs to keep the demo lightweight, runnable, and focused:

* **Synchronous Execution:** The sub-queries and evaluation steps run sequentially. In a real production system, independent branches would be parallelized using `asyncio` to reduce latency (Time-To-First-Token).
* **No Cross-Encoder Re-ranker:** When the `ReflectionAgent` expands the context across multiple loops, the context window can grow large. In production, a lightweight Re-ranker (like `Cohere` or a local `cross-encoder`) would be injected after the `EvidenceAgent` to discard low-signal chunks and protect the LLM context window. We skipped this to minimize heavy local ML dependencies.
* **Massive Input Truncation vs. Compression:** We assume reasonable input sizes. For production, inputs of thousands of words would trigger a `QueryCompressionAgent` before routing, and massive contexts would trigger a Map-Reduce evaluation step to avoid API crashes. We rely on the natural efficiency of the exact-match-first strategy here.
* **CLI vs. API:** The system operates as a stateful CLI script rather than an asynchronous web framework (like FastAPI).

## Router Contract

The router may create multiple retrieval queries only to isolate branches of the original question or nearby equivalent phrasing. It must not add new meaning.

Each retrieval query contains:

```json
{
  "query_id": "Q2",
  "query": "AWS customer responsibilities for account security",
  "purpose": "account responsibility evidence",
  "target_sections": [],
  "include_references": false
}
```

`Q1` is always the original question unchanged.

Run:

```bash
venv/bin/python query/agents/query_cli.py "What are customer responsibilities and what happens to customer content?" --trace --show-branches
```

From `query/`, the helper script starts Neo4j, checks the embedding/chat models, and runs the CLI with trace logs:

```bash
./run_query.sh "What are customer responsibilities?"
./run_query.sh --interactive
```

Inspect retrieval without answer generation:

```bash
venv/bin/python query/agents/query_cli.py "What are customer responsibilities?" --no-answer --show-context
```

Limit router branching:

```bash
venv/bin/python query/agents/query_cli.py "..." --max-queries 3
```

## Evaluation Questions

`questions.txt` contains manual test questions for the AWS Customer Agreement. Each item includes:

- a user-facing question
- the expected answer
- supporting section references

The file starts with simple direct lookups and gradually moves into multi-section and edge-case questions for testing router branching, retrieval, subanswers, and verification.

Useful environment variables:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
OPENAI_EMBEDDING_BASE_URL=http://localhost:11434/v1
OPENAI_EMBEDDING_MODEL=qwen3-embedding:4b
OPENAI_CHAT_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_CHAT_MODEL=google/gemma-4-31b-it
NVIDIA_API_KEY=your-nvidia-api-key
```

`query/agents/.env` stores non-secret defaults for Ollama embeddings and NVIDIA chat. Export `NVIDIA_API_KEY` in your shell before running queries; do not commit real API keys.
