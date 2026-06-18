# Query Pipeline

## Purpose

- Owns the document-to-graph query/RAG pipeline for the job assessment.
- Converts source PDFs into a Document/Section/Chunk graph, ingests that graph into Neo4j, creates EmbeddingChunk vector nodes, and checks graph state.

## Ownership

- `run_pipeline.sh` orchestrates the full local pipeline.
- `run_query.sh` starts query dependencies and runs the multi-agent query CLI with trace logging.
- `check_graph.py` verifies Neo4j graph shape and vector presence.
- `step 1/` owns PDF parsing, `document_graph.json` generation, and graph JSON validation.
- `step 2/substep1_infrastructure/` owns Neo4j Docker infrastructure.
- `step 2/substep2_graph_ingestion/` owns Document/Section/Chunk graph ingestion.
- `step 2/substep3_vector_embedding/` owns LM Studio semantic splitting and EmbeddingChunk vector ingestion.
- `agents/` owns task-specific query agents and the testing CLI.

## Local Contracts

- Keep pipeline paths compatible with folder names that contain spaces.
- Neo4j defaults are `bolt://localhost:7687` with `neo4j/password123` unless a task explicitly changes local infrastructure.
- `step 1/document_graph.json` is generated from `resources/AWS Customer Agreement.pdf` and consumed by Step 2 ingestion.
- Step 1 hierarchy must use `Document -> Section -> Chunk`.
- Step 1 references must target stable `Section` IDs, not chunk IDs.
- Step 1 chunk reference metadata must stay reciprocal: `referenced_section_ids` outbound links and `referenced_by_chunk_ids` inbound links.
- Step 2 graph nodes are `Document`, `Section`, `Chunk`, and `EmbeddingChunk`.
- Embedding nodes use `EmbeddingChunk` with `embedding` vectors and `HAS_EMBEDDING` relationships from `Chunk`.
- Treat files named `test_*.py` here as exploratory smoke scripts unless a formal test framework is added.

## Work Guidance

- Prefer environment variables for external API keys, model names, and base URLs; do not add real secrets to source files.
- Preserve the three-stage workflow: document processing, graph ingestion, vector embedding.
- Use scripts already present before introducing new orchestration.
- Keep README instructions aligned with runnable commands when changing behavior.

## Verification

- For document parsing changes, run `venv/bin/python "query/step 1/document_processor.py"` and `venv/bin/python "query/step 1/document_processor.py" --validate-only`.
- For graph ingestion changes, ensure Neo4j is running, then run the affected ingestion script.
- For vector embedding changes, verify the selected embedding backend is available before running the embed script.
- For full pipeline changes, run `query/run_pipeline.sh` from `query/`.
- For query script changes, run `query/run_query.sh --help`.
- Use `venv/bin/python query/check_graph.py` after ingestion/vector work when Neo4j and LM Studio are available.

## Child DOX Index

- `agents/AGENTS.md` - Task-specific query agents, Neo4j retrieval tools, and the local query CLI.
