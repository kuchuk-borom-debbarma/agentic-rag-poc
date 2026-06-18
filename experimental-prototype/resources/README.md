# Resources

This directory contains source PDFs used by the query/RAG pipeline.

## Files

- `AWS Customer Agreement.pdf` is the main source document parsed into the graph.
- `Junior_AI_Developer_Task_Vestaff.pdf.pdf` is the assessment/task context material.

## Rules

- Keep source filenames stable unless all dependent pipeline paths are updated.
- Do not store generated graph JSON or embeddings here.
- Derived artifacts belong under `query/`.

## After Replacing a Source PDF

Regenerate and validate the document graph:

```bash
venv/bin/python "query/step 1/document_processor.py"
venv/bin/python "query/step 1/document_processor.py" --validate-only
```
