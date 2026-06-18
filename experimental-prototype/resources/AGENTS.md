# Resources

## Purpose

- Owns source documents used by the query/RAG assessment pipeline.

## Ownership

- `AWS Customer Agreement.pdf` is the current pipeline input for structural chunking.
- `Junior_AI_Developer_Task_Vestaff.pdf.pdf` is assessment/task context material.

## Local Contracts

- Preserve filenames expected by pipeline scripts unless all dependent paths are updated together.
- Treat PDFs as source material; derived JSON and graph data belong under `query/`.

## Work Guidance

- Do not modify source PDFs unless explicitly asked.
- When replacing a PDF input, update pipeline docs and paths in the same change.

## Verification

- After source PDF changes, rerun the relevant document processing script and inspect generated chunk output.

## Child DOX Index

- No child AGENTS.md files.
