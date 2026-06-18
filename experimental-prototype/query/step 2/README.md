# Step 2: Neo4j Graph and Embeddings

This step turns `query/step 1/document_graph.json` into a searchable Neo4j graph with vector embeddings.

## Sub-steps

1. `substep1_infrastructure/` starts Neo4j with Docker Compose.
2. `substep2_graph_ingestion/` loads Document, Section, and Chunk nodes plus graph relationships.
3. `substep3_vector_embedding/` creates EmbeddingChunk nodes and the `semantic_embeddings` vector index.

## Expected Graph Shape

```text
Document -[:HAS_SECTION]-> Section
Section  -[:HAS_SECTION]-> Section
Section  -[:HAS_CHUNK]-> Chunk
Chunk    -[:NEXT_CHUNK]-> Chunk
Chunk    -[:REFERENCES]-> Section
Chunk    -[:HAS_EMBEDDING]-> EmbeddingChunk
```

## Run Through Pipeline

The preferred path is the top-level query script:

```bash
cd query
./run_pipeline.sh
```

## Verify

From the repo root:

```bash
venv/bin/python query/check_graph.py
```
