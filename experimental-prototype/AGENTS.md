# Prototype Pipeline

## Purpose
- Owns the experimental Neo4j graph and LangGraph-based RAG pipeline.
- Groups all prototype resources, documentation, and queries in one place, separate from the final clean app.

## Ownership
- `query/` owns document processing, graph ingestion, embedding, verification scripts, and query agents.
- `resources/` owns source PDFs consumed by the prototype pipeline.
- `DOCUMENTATION_DETAILED.md` owns the detailed walkthrough of the prototype.
- `README.md` owns prototype-specific setup and commands.

## Local Contracts
- Do not use this prototype code in the final `app/` assessment.
- Neo4j must be running locally for the pipeline to work.

## Work Guidance
- Use this area only for complex RAG/Graph experimentation.

## Verification
- Graph shape verification: `../venv/bin/python query/check_graph.py`

## Child DOX Index
- `query/AGENTS.md` - Sub-pipeline rules for the query system.
- `resources/AGENTS.md` - Source PDFs and assessment materials consumed by the prototype.
