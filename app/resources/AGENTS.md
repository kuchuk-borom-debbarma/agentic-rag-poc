# App Resources

## Purpose

- Owns source documents bundled with the standalone final assessment app.

## Ownership

- `AWS Customer Agreement.pdf` is the app-local RAG source document used by backend ingestion.

## Local Contracts

- Keep final app resources inside `app/resources/` so `app/` remains independent from resources outside the app.
- Preserve source filenames expected by app config unless dependent docs and defaults are updated together.
- Treat PDFs as source material; generated vector stores and SQLite data belong under `app/backend/data/`.

## Work Guidance

- Do not modify source PDFs unless explicitly asked.
- When replacing the RAG source PDF, update `app/backend/.env.example`, backend config defaults, and app docs in the same change.

## Verification

- After source PDF changes, run backend ingest against the app-local PDF and confirm chunk count is nonzero.

## Child DOX Index

- No child AGENTS.md files.
