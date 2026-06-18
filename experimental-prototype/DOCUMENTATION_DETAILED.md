# Detailed RAG and Query Flow Documentation

This document explains how this project turns the AWS Customer Agreement PDF into a graph-backed RAG system, how the query loop answers questions, why the current design choices were made, what is covered today, and what is not covered yet.

The system is intentionally local and inspection-friendly. It is built for a job assessment proof of concept, not as a finished production service.

## High-Level Pipeline

```text
resources/AWS Customer Agreement.pdf
  -> query/step 1/document_graph.json
  -> Neo4j Document/Section/Chunk graph
  -> EmbeddingChunk vector nodes and semantic_embeddings index
  -> query/agents/query_cli.py multi-agent query loop
```

The project has two main flows:

1. RAG ingestion flow: parse the PDF, build a structured graph model, ingest it into Neo4j, and create vector-searchable embedding nodes.
2. Query flow: route a user question, retrieve evidence, expand evidence through graph relationships, answer with citations, verify grounding, optionally retry retrieval, and synthesize a final answer.

## What We Cover Today

- Single-document ingestion for `resources/AWS Customer Agreement.pdf`.
- Structural extraction into `Document`, `Section`, and `Chunk` records.
- Stable section IDs such as `section_2_2`, which make section references durable.
- Cross-reference detection for text like `Section 2.2`.
- Reciprocal JSON reference metadata for validation: outbound `referenced_section_ids` and inbound `referenced_by_chunk_ids`.
- Neo4j graph materialization with uniqueness constraints.
- Ordered chunk traversal through `NEXT_CHUNK`.
- Section hierarchy traversal through `HAS_SECTION`.
- Chunk-to-section ownership through `HAS_CHUNK`.
- Chunk-to-referenced-section links through `REFERENCES`.
- Semantic embedding nodes through `EmbeddingChunk`.
- Native Neo4j vector index named `semantic_embeddings`.
- OpenAI-compatible embedding and chat clients.
- Environment-driven model and endpoint configuration for the query agent.
- CLI-based query testing with trace output.
- Question decomposition through `RouterAgent`.
- Vector retrieval through `SemanticSearchAgent`.
- Graph context expansion through `EvidenceAgent`.
- Branch answers and final synthesis through `AnswerAgent`.
- Deterministic citation checks and optional LLM support checks through `VerifierAgent`.
- One reflection retry through `ReflectionAgent` when the final answer fails verification.

## RAG Ingestion Flow

### 1. Source Document

Input document:

```text
resources/AWS Customer Agreement.pdf
```

The pipeline assumes this PDF is the source of truth. The root README and query README both describe this as the current document input.

Why this design:

- A single known PDF keeps the assessment reproducible.
- File-name stability keeps scripts simple.
- Source PDFs stay under `resources/`; generated graph and query artifacts stay under `query/`.

What is not covered:

- Dynamic document upload.
- Multiple document collections.
- Versioned document replacement.
- Document metadata such as jurisdiction, publication date, account type, or customer segment.

### 2. PDF Parsing

Owner:

```text
query/step 1/document_processor.py
```

The parser uses `pymupdf4llm.to_markdown(..., page_chunks=True)` and reads layout `page_boxes`. It ignores box classes that are not useful for the graph:

```python
IGNORED_BOX_CLASSES = {"page-header", "page-footer", "picture"}
```

For each useful layout box, it stores:

- text
- box class
- page start
- page end

Why this design:

- Layout boxes preserve document order better than plain text extraction.
- Ignoring headers and footers reduces repeated boilerplate in retrieval.
- Page numbers are preserved so answers can cite source location later.

What is not covered:

- OCR for scanned PDFs.
- Table extraction as structured rows and columns.
- Image extraction or captioning.
- Footnote-specific parsing.
- Header/footer recovery when those areas contain legally important text.
- Human review of parsing quality.

### 3. Section Detection

The parser identifies numbered headings with regular expressions:

```python
MAJOR_SEC_RE = re.compile(r"^#*\s*\**(\d+)\.\s+(.+)")
MINOR_SEC_RE = re.compile(r"^#*\s*\**(\d+\.\d+)\s+(.+)")
```

Examples:

- `1. Use of the Service Offerings`
- `2.2 Your Content`

The parser builds section IDs with `section_id()`:

```text
2   -> section_2
2.2 -> section_2_2
```

Text before the first numbered section goes into:

```text
section_front_matter
```

Why this design:

- Contract documents often have meaningful numbered sections.
- Stable section IDs are better than relying on chunk IDs, because chunk boundaries can change.
- Section-level references let the graph follow legal cross-references even when wording changes.

What is not covered:

- Deep heading levels beyond `N.N`.
- Lettered sections like `(a)`, `(b)`, or appendix labels.
- Roman numerals.
- Heading detection for unnumbered legal clauses.
- Ambiguous cases where a sentence begins with a number but is not a heading.
- Section titles split across multiple layout boxes.

### 4. Chunk Creation

Every extracted content block becomes a `Chunk`. Chunks are assigned:

- `chunk_id`
- `section_id`
- `section_number`
- `text`
- `chunk_type`
- `order`
- `page_start`
- `page_end`
- `previous_chunk_id`
- `next_chunk_id`
- `referenced_section_ids`
- `referenced_by_chunk_ids`

Chunk IDs are sequential:

```text
chunk_0000
chunk_0001
chunk_0002
```

The chunk order is also used later for neighborhood expansion in query-time retrieval.

Why this design:

- Chunk IDs are deterministic for a given parse output.
- `previous_chunk_id` and `next_chunk_id` preserve local reading order.
- Keeping original chunk text separate from embedding chunks lets the system preserve a faithful document graph while still creating smaller semantic search units.

What is not covered:

- Token-count-aware chunk sizing.
- Overlap windows at ingestion time.
- Paragraph-level confidence scores.
- Stable chunk identity across parser changes.
- Deduplication of repeated clauses.
- Language detection.

### 5. Reference Resolution

The parser scans chunk text with:

```python
SECTION_REF_RE = re.compile(r"Section\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
```

If a chunk mentions `Section 2.2`, the parser maps it to:

```text
section_2_2
```

The generated JSON stores:

- source chunk outbound references in `referenced_section_ids`
- target chunk inbound references in `referenced_by_chunk_ids`

In Neo4j, the durable relationship is:

```text
(:Chunk)-[:REFERENCES]->(:Section)
```

Why this design:

- Legal answers often require following "subject to Section X" style references.
- Section-level references are more stable than chunk-level references.
- Reciprocal JSON metadata makes validation possible before Neo4j ingestion.

What is not covered:

- References without the word `Section`.
- Multiple ranges like `Sections 2.1 through 2.4`.
- References to exhibits, addenda, policies, URLs, or external service terms.
- Cross-document references.
- References to definitions by term rather than section number.
- Automatic fetch of all referenced section chunks; current graph tool fetches only the first two chunks of each referenced section.

### 6. Graph JSON Validation

`validate_graph()` checks graph invariants before writing the JSON and when run with `--validate-only`.

It verifies:

- document ID exists
- section parent IDs exist
- section child IDs exist
- section chunk IDs exist
- chunk order is continuous from `0`
- chunk section IDs exist
- previous and next chunk IDs exist
- referenced section IDs exist
- inbound `referenced_by_chunk_ids` match expected outbound references

Why this design:

- Bad graph JSON should fail before it reaches Neo4j.
- JSON validation gives a fast local check that does not require Docker or model servers.
- Reference reciprocity catches subtle graph mistakes early.

What is not covered:

- JSON Schema validation during runtime, even though `schema.json` exists.
- Semantic validation that extracted text is correct.
- Gold-set validation against known section counts or expected headings.
- Page-order validation against PDF coordinates.
- Regression tests for parser output.

### 7. Neo4j Ingestion

Owner:

```text
query/step 2/substep2_graph_ingestion/ingest_parents.py
```

The ingestion script:

1. Loads `query/step 1/document_graph.json`.
2. Connects to Neo4j at `bolt://localhost:7687`.
3. Creates uniqueness constraints.
4. Clears the existing database.
5. Creates one `Document` node.
6. Creates all `Section` nodes.
7. Creates all `Chunk` nodes.
8. Creates hierarchy and traversal relationships.
9. Prints graph counts.

Graph shape:

```text
Document -[:HAS_SECTION]-> Section
Section  -[:HAS_SECTION]-> Section
Section  -[:HAS_CHUNK]-> Chunk
Chunk    -[:NEXT_CHUNK]-> Chunk
Chunk    -[:REFERENCES]-> Section
```

Why this design:

- Neo4j makes hierarchy, neighboring chunks, and legal cross-references queryable.
- Clearing the database keeps local assessment runs deterministic.
- Constraints prevent accidental duplicate IDs.

What is not covered:

- Incremental ingestion.
- Partial re-ingestion of changed sections.
- Multi-tenant graph isolation.
- Soft deletes.
- Historical versions.
- Transaction batching for very large documents.
- Safety guard against clearing a shared database.
- Environment-driven Neo4j settings in this ingestion script; it currently uses hardcoded local defaults.

### 8. Embedding and Vector Indexing

Owner:

```text
query/step 2/substep3_vector_embedding/embed_children.py
```

The embedding script:

1. Loads embedding configuration from environment.
2. Checks the embedding backend.
3. Connects to Neo4j.
4. Fetches all `Chunk` nodes.
5. Uses `SemanticChunker` to split chunk text into smaller semantic pieces.
6. Creates one or more `EmbeddingTask` records per source chunk.
7. Drops and recreates the vector index.
8. Deletes old `EmbeddingChunk` nodes.
9. Embeds each task text.
10. Inserts each `EmbeddingChunk`.
11. Links it back to the source `Chunk`.

Relationship:

```text
(:Chunk)-[:HAS_EMBEDDING]->(:EmbeddingChunk)
```

The vector index is:

```text
semantic_embeddings
```

The vector dimension is detected dynamically from a test embedding.

Why this design:

- Source chunks preserve document structure.
- Embedding chunks can be smaller and more semantically focused.
- Keeping embedding nodes separate from source chunks allows multiple embedding models or re-embedding strategies later.
- Neo4j native vector search keeps retrieval close to graph expansion.

What is not covered:

- Embedding cache.
- Retry with exponential backoff.
- Rate-limit handling.
- Batch embedding requests.
- Parallel embedding.
- Multiple embedding models at once.
- Embedding version metadata beyond model and dimension.
- Deleting only stale embeddings for changed chunks.
- Reusing an existing index when dimension is unchanged.
- Production monitoring of embedding failures.

### 9. Pipeline Orchestration

Owner:

```text
query/run_pipeline.sh
```

The full pipeline:

1. Starts Neo4j through Docker Compose.
2. Waits for Neo4j connectivity.
3. Builds `document_graph.json`.
4. Validates graph invariants.
5. Ingests the graph into Neo4j.
6. Checks embedding backend health.
7. Vectorizes chunks.
8. Verifies the final Neo4j graph.

Why this design:

- One script gives a reproducible local run.
- Each stage remains independently runnable for debugging.
- Step numbers in output help identify failed stage quickly.

What is not covered:

- CI pipeline integration.
- Containerized Python runtime.
- Dependency lock enforcement.
- Cloud deployment.
- Scheduling.
- Observability dashboards.
- Restart/resume from failed stage.

## Query Flow

### 1. CLI Entry Point

Owner:

```text
query/agents/query_cli.py
```

The query CLI accepts:

- question text
- `--top-k`
- `--neighbors`
- `--max-queries`
- `--trace`
- `--trace-hits`
- `--show-context`
- `--show-branches`
- `--no-answer`
- `--skip-llm-verifier`

The helper script:

```text
query/run_query.sh
```

can start Neo4j, check model health, and run the CLI with trace output.

Why this design:

- A CLI is fast to test and easy to inspect.
- Trace output makes each agent stage visible.
- `--no-answer` supports retrieval debugging without spending chat tokens.

What is not covered:

- Web UI.
- API server.
- Streaming answer output.
- Authentication.
- Per-user sessions.
- Conversation history.
- Feedback capture from users.

### 2. Configuration

Owner:

```text
query/agents/config.py
```

Configuration is loaded from:

- repository `.env`
- embedding `.env`
- agents `.env`
- process environment

Defaults include:

```text
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
OPENAI_EMBEDDING_BASE_URL=http://localhost:11434/v1
OPENAI_EMBEDDING_MODEL=qwen3-embedding:4b
OPENAI_CHAT_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_CHAT_MODEL=google/gemma-4-31b-it
```

Why this design:

- The same OpenAI-compatible client can call local tools, Ollama-style endpoints, LM Studio-style endpoints, or hosted providers.
- Secrets are expected to come from environment variables.
- Query-time configuration is more flexible than ingestion-time configuration.

What is not covered:

- Config validation with friendly error messages for every field.
- Secret manager integration.
- Per-environment config profiles.
- Runtime model fallback.
- Cost budgets.

### 3. OpenAI-Compatible Client

Owner:

```text
query/agents/llm_client.py
```

The client has two calls:

- `embed(model, text)`
- `chat(model, messages, temperature=0.1)`

It expects OpenAI-compatible JSON responses.

Why this design:

- Keeps model vendor coupling low.
- Avoids SDK-specific code.
- Makes local and hosted backends interchangeable if they implement `/embeddings` and `/chat/completions`.

What is not covered:

- Streaming chat responses.
- Tool calling.
- Structured-output schema enforcement beyond best-effort JSON parsing.
- Provider-specific retry and error classification.
- Token counting before requests.

### 4. RouterAgent

Owner:

```text
query/agents/agents.py
```

The router creates a `RoutePlan`:

- intent
- complexity
- original question
- retrieval queries
- top-k
- neighbors
- warnings

It uses two paths:

1. Heuristic routing for simple questions and fallback.
2. LLM routing for compound or complex questions when a chat model is available.

The heuristic router:

- extracts explicit section references like `Section 2.2`
- splits questions on conjunctions such as `and`, `also`, `while`, `but`, `versus`, and `vs`
- marks some queries as needing references if they mention terms like `refer`, `reference`, `linked`, `related`, `depend`, or `affect`

Why this design:

- Simple questions should not need an LLM router.
- Compound questions often need separate retrieval branches.
- A deterministic fallback keeps the system usable when the router LLM fails.

What is not covered:

- Query planning based on actual graph schema statistics.
- Entity extraction beyond section references.
- Synonym expansion controlled by a glossary.
- Multi-hop planning beyond basic reference-following hints.
- User intent memory across turns.
- Detecting unsupported or out-of-scope questions before retrieval.

### 5. SemanticSearchAgent

The semantic search agent:

1. Embeds each retrieval query.
2. Calls Neo4j vector search:

```text
CALL db.index.vector.queryNodes('semantic_embeddings', top_k, embedding)
```

3. Joins each matched `EmbeddingChunk` back to its parent `Chunk`.
4. Returns chunk text, section metadata, page metadata, order, and similarity score.

Why this design:

- Embedding search handles paraphrase and semantic similarity.
- Joining back to `Chunk` gives full source text and graph metadata.
- Neo4j keeps vector retrieval and graph traversal in one database.

What is not covered:

- Keyword/BM25 search.
- Hybrid search.
- Query expansion through definitions.
- Cross-encoder reranking.
- Score threshold tuning.
- Per-section filters.
- Metadata filters.
- Diversity-aware retrieval.

### 6. EvidenceAgent

The evidence agent expands raw vector matches into context blocks.

It can add:

- exact section chunks if the query explicitly targeted a section number
- neighboring chunks around matched chunk orders
- referenced section chunks when `include_references` is true

Important implementation detail:

- Neighbor expansion uses numeric `Chunk.order` windows, not the `NEXT_CHUNK` relationship.
- Referenced-section expansion currently returns only the first two chunks from each referenced section.
- Context blocks are deduplicated and then sorted by source order.

Why this design:

- Vector hits alone may miss nearby legal context.
- Exact section lookup makes `Section 2.2` questions reliable.
- Reference following adds legal cross-reference awareness.
- Deduplication keeps repeated retrieval branches from flooding context.

What is not covered:

- Graph traversal depth beyond direct references.
- Recursive reference following.
- Full referenced-section retrieval.
- Learned context packing.
- Reranking after expansion.
- Token budget management.
- Detecting contradictory evidence.
- Guarantee that the highest-scoring semantic hit survives deduplication when a non-scored duplicate appears later.

### 7. AnswerAgent

The answer agent runs in two modes:

1. Branch answer mode: answer one retrieval branch using that branch context.
2. Final answer mode: synthesize the final answer from verified branch answers and merged context.

Prompts instruct the model to:

- use only provided context
- avoid assumptions and outside knowledge
- cite every factual claim with source IDs like `[S1]`
- state when evidence is missing

Why this design:

- Branch answers make compound questions easier to verify.
- Final synthesis can combine multiple verified branches.
- Citation requirements make answer grounding inspectable.

What is not covered:

- Hard enforcement that every sentence has a citation.
- Quote extraction tied to citations.
- Faithfulness scoring by claim.
- Answer style templates.
- Numeric or date normalization.
- Citation spans mapped to exact character offsets.

### 8. VerifierAgent

The verifier has two layers:

1. Deterministic checks:
   - answer is not empty
   - answer has citations unless it says material was not found
   - cited source IDs exist in the provided context
2. Optional LLM support check:
   - asks a chat model whether the answer is supported by the context
   - returns issues if unsupported

Why this design:

- Deterministic citation validation catches easy failures cheaply.
- LLM verification catches unsupported claims that still cite valid source IDs.
- Verification output can trigger reflection.

What is not covered:

- Independent verifier model isolation from answer model.
- Claim-by-claim verification.
- Exact evidence span matching.
- Calibration of confidence values.
- Regression evals for verifier accuracy.
- Protection from verifier model false positives or false negatives.

### 9. ReflectionAgent

If the final answer fails verification, the orchestrator allows one retry.

The reflection agent:

1. Reads verification issues.
2. Asks the chat model for updated retrieval settings.
3. Can add one or two new targeted retrieval queries.
4. Can increase neighbor expansion.
5. Can enable reference-following.
6. Returns an updated `RoutePlan`.

Fallback behavior:

- If reflection fails, it enables references and increases neighbors to at least `1`.

Why this design:

- Some retrieval failures need a second search pass.
- Verification issues provide useful signals for targeted search.
- Limiting retries prevents runaway loops.

What is not covered:

- Multiple iterative retries.
- Reflection based on branch-level failures before final synthesis.
- Cost-aware retry decisions.
- Automatic lowering or raising of `top_k`.
- Detecting when retry cannot help.
- Persisting failed query traces for offline evaluation.

### 10. Final Output

The CLI prints:

- optional trace output
- optional branch answers
- final answer
- sources
- final verification result
- optional full retrieved context

Why this design:

- The output is meant for development and assessment review.
- It favors transparency over polished UX.
- Trace output helps debug routing, retrieval, evidence expansion, answering, and verification.

What is not covered:

- End-user-friendly formatting.
- Source preview UI.
- Clickable citations.
- Exportable reports.
- Audit log storage.

## Why This Architecture

### Why Graph + Vector Instead of Plain Vector RAG

Plain vector RAG is good at finding semantically similar text, but legal and contractual documents often require structure:

- sections contain obligations
- subsections depend on parent sections
- neighboring chunks provide conditions and exceptions
- references point to other legal sections
- users may ask for a specific section

The graph gives the system a way to retrieve structure, not only semantic similarity.

### Why Preserve Document/Section/Chunk Separately From EmbeddingChunk

`Chunk` nodes represent source structure. `EmbeddingChunk` nodes represent search units.

This separation matters because:

- source structure should remain stable and readable
- embedding chunks can change when the embedding model or semantic splitter changes
- multiple embeddings per source chunk are possible
- future systems could add multiple embedding models without changing source nodes

### Why Multi-Agent Query Flow

The "agents" here are small task-specific stages, not autonomous general agents. Each one owns a narrow step:

- route the question
- retrieve candidates
- collect evidence
- answer a branch
- verify an answer
- reflect on failure
- synthesize final answer

This makes the flow easier to inspect, debug, and improve than one large prompt that does everything.

### Why CLI First

The project is still validating retrieval and grounding quality. A CLI gives:

- fast iteration
- visible traces
- fewer moving parts
- direct access to debugging flags

A web app or API can come later once retrieval behavior is reliable.

## Edge Cases Not Covered Yet

### Document Parsing Edge Cases

- scanned PDFs requiring OCR
- complex tables
- multi-column layouts
- footnotes
- appendices
- definitions sections with terms not referenced by section number
- section numbers deeper than two levels
- section titles split across lines or boxes
- repeated section titles
- legal references written as `Sections 2.1-2.4`
- external links and policy references
- PDF extraction order errors

### Graph Modeling Edge Cases

- multiple documents in one graph
- multiple versions of the same agreement
- document amendments
- section renumbering across versions
- overlapping chunk ownership
- references to specific clauses inside a section
- references to non-section objects such as URLs, policies, forms, addenda, or services
- deleting or replacing one document without clearing the database

### Retrieval Edge Cases

- query asks for exact wording and vector search retrieves a paraphrase
- query uses legal synonyms not present in the document
- query needs a definition in one section and an obligation in another
- query requires all exceptions, but `top_k` retrieves only common clauses
- query requires a full referenced section, but current reference expansion fetches only first two chunks
- query asks "what is not allowed" and relevant text is phrased positively
- query asks about a section number that does not exist
- query asks for a term that appears in many sections
- query requires comparison across far-apart sections

### Answering Edge Cases

- answer cites a valid source but overstates it
- answer needs exact quote, not summary
- answer needs "not found" but retrieval finds adjacent irrelevant text
- answer requires counting all occurrences
- answer requires date or numeric calculation
- answer requires resolving ambiguity between AWS, customer, affiliates, or end users
- answer should identify uncertainty rather than produce a confident synthesis

### Verification Edge Cases

- verifier model may miss unsupported claims
- verifier model may reject valid paraphrases
- deterministic citation checks do not prove a claim is supported
- final answer may be supported by merged context but not by branch answer
- branch answer may fail while final answer still sounds reasonable
- reflection only runs once

## Scaling Things We Do Not Cover Yet

### Data Scale

Not covered:

- thousands of PDFs
- incremental document updates
- sharded or partitioned graph storage
- large batch embedding jobs
- embedding queues
- distributed workers
- storage lifecycle management

Needed for scale:

- document IDs and collection IDs
- metadata filters
- chunk and embedding versioning
- incremental ingestion
- idempotent upserts
- batch and async embedding
- ingestion job tracking

### Query Scale

Not covered:

- concurrent users
- async retrieval branches
- request cancellation
- streaming output
- result caching
- query-level timeouts across all stages
- rate-limit management
- token budget controls

Needed for scale:

- async agent execution
- caching for embeddings and retrieval results
- parallel branch retrieval
- bounded context packing
- retry policies
- API service layer
- tracing and metrics

### Evaluation Scale

Not covered:

- automated golden question set execution
- precision/recall metrics
- answer faithfulness metrics
- retrieval hit-rate checks
- hallucination-rate tracking
- regression dashboard

Needed for scale:

- test questions with expected source sections
- offline retrieval evaluation
- answer grading rubric
- model comparison harness
- prompt/version tracking

### Operational Scale

Not covered:

- production secrets management
- backups
- database migrations
- deployment automation
- user authentication
- authorization by document collection
- observability
- error reporting
- audit logging

Needed for scale:

- service config management
- managed Neo4j or equivalent graph store plan
- logging and metrics
- structured traces per query
- secure secret storage
- deployment environment separation

## Known Implementation Limits

- `ingest_parents.py`, `embed_children.py`, and `check_graph.py` use local Neo4j defaults directly.
- `ingest_parents.py` clears the whole database before loading.
- `query/agents/query_cli.py` runs branches sequentially.
- Reflection retry count is fixed to one retry.
- No formal test framework is present; `test_*.py` files are exploratory smoke scripts.
- No package manifest or lock file is visible in the repository root.
- `query/agents/AGENTS.md` currently contains duplicated trailing text.
- The system assumes the embedding index already exists before query-time vector search.
- `GraphTools.get_referenced_sections()` returns only the first two chunks from each referenced section.
- Context deduplication is simple and does not rerank after expansion.

## Verification Commands

Run parser and JSON validation:

```bash
venv/bin/python "query/step 1/document_processor.py"
venv/bin/python "query/step 1/document_processor.py" --validate-only
```

Run full pipeline from `query/`:

```bash
./run_pipeline.sh
```

Check graph after ingestion and embedding:

```bash
venv/bin/python query/check_graph.py
```

Run query CLI help:

```bash
venv/bin/python query/agents/query_cli.py --help
```

Run retrieval-only debugging:

```bash
venv/bin/python query/agents/query_cli.py "What are customer responsibilities?" --no-answer --show-context
```

Run full query with traces:

```bash
venv/bin/python query/agents/query_cli.py "What are customer responsibilities?" --trace --show-branches
```

## Practical Next Steps

Highest-value improvements:

1. Add a small golden question set with expected source sections.
2. Add hybrid retrieval with keyword search plus vector search.
3. Add reranking after graph expansion.
4. Make Neo4j settings environment-driven in ingestion, embedding, and check scripts.
5. Add token-budget-aware context packing.
6. Make referenced-section expansion configurable.
7. Add parser regression tests for section detection and references.
8. Add batch embedding and retry handling.
9. Store query traces for evaluation.
10. Build an API only after retrieval quality is measured.
