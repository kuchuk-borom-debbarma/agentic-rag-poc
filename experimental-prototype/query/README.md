# Query Pipeline

This directory owns the full local query/RAG pipeline.

## Stages

1. `step 1/` parses `resources/AWS Customer Agreement.pdf` into `document_graph.json`.
2. `step 2/substep1_infrastructure/` starts local Neo4j.
3. `step 2/substep2_graph_ingestion/` ingests Document, Section, and Chunk nodes.
4. `step 2/substep3_vector_embedding/` creates EmbeddingChunk vectors and the Neo4j vector index.
5. `agents/` runs the small task-specific query agents.

## Run Everything

```bash
./run_pipeline.sh
```

This script expects to run from `query/` and uses `../venv/bin/python`.

## Verify Generated Graph JSON

From the repo root:

```bash
venv/bin/python "query/step 1/document_processor.py" --validate-only
```

## Verify Neo4j Graph

After ingestion and embedding:

```bash
venv/bin/python query/check_graph.py
```

## Test Query Agents

From the repo root:

```bash
venv/bin/python query/agents/query_cli.py "What are customer responsibilities?" --trace --show-branches
```

Or use the helper script from `query/`, which starts Neo4j, checks the embedding/chat models, and enables trace logs:

```bash
cd query
export NVIDIA_API_KEY=your-nvidia-api-key
./run_query.sh "What are customer responsibilities?"
```

Interactive mode prompts for the question and tuning options:

```bash
./run_query.sh --interactive
```

The helper passes extra arguments through to the CLI:

```bash
./run_query.sh "What are customer responsibilities and what happens to customer content?" --max-queries 4 --show-context
```

Use retrieval-only mode when tuning search quality:

```bash
venv/bin/python query/agents/query_cli.py "What are customer responsibilities?" --no-answer --show-context
```
