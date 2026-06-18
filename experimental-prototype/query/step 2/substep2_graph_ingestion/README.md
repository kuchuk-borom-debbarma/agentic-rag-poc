# Sub-step 2: Graph Ingestion

## Goal

Load `query/step 1/document_graph.json` into Neo4j as a clean document graph.
This replaces the previous chunk-only model with explicit `Document`, `Section`, and `Chunk` nodes.

## Graph Model

Nodes:

```text
(:Document)
(:Section)
(:Chunk)
```

Relationships:

```text
Document -[:HAS_SECTION]-> Section
Section  -[:HAS_SECTION]-> Section
Section  -[:HAS_CHUNK]-> Chunk
Chunk    -[:NEXT_CHUNK]-> Chunk
Chunk    -[:REFERENCES]-> Section
```

## Approach

`ingest_parents.py` is organized as small ingestion steps:

1. Load graph JSON.
2. Connect to Neo4j.
3. Create uniqueness constraints.
4. Clear old graph data.
5. Create all nodes.
6. Create hierarchy relationships.
7. Create chunk ordering relationships.
8. Create reference relationships.
9. Print final node and relationship counts.

## Why References Target Sections

Contract text usually says `Section 2.2`, not a specific extracted chunk. The target is therefore the stable section node:

```text
Chunk 1.3.0 -[:REFERENCES]-> Section 2.2
```

This keeps references stable if chunking changes later.

## Run

Ensure Neo4j is running, then:

```bash
../../../venv/bin/python ingest_parents.py
```

After ingestion, verify from the repo root:

```bash
./venv/bin/python query/check_graph.py
```
