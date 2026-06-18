# Backend Assessment App

## Purpose

- Owns the Contract-First Modular FastAPI backend for the AWS Customer Agreement RAG assessment.
- Enforces strict bounded-context service architecture as defined in `rules/code-base.md`.

## Ownership

- `config/` owns settings, DI container, FastAPI dependency providers, and global exception handlers.
- `routes/` owns thin HTTP route handlers; no business logic.
- `services/<name>/public/` owns service contracts (Protocols), public models, and public errors.
- `services/<name>/internal/` owns service implementations and internal port definitions.
- `services/rag/internal/ingestion/` owns the staged RAG ingestion rebuild: layout extraction, hierarchical parsing, semantic chunking, graph maps, and vector persistence ports.
- `infra/` owns concrete adapters for external systems (Chroma, SQLite analytics, SQLite graph maps, OpenAI, PDF loading).
- `models/domain.py` owns shared domain types used across bounded contexts.
- `main.py` owns the application factory and lifespan container setup.

## Local Contracts

- Routes must import only from `services/<name>/public/` — never from `internal/`.
- Services must import only from their own `internal/ports.py` — never from `assessment_app.infra` directly.
- Concrete infra classes must only be imported in `config/container.py`.
- Services must not raise `HTTPException` — only domain errors from `public/errors.py`.
- Global exception handlers in `config/exception_handlers.py` map domain errors to HTTP responses.
- `config/container.py` is the sole composition root.

## Work Guidance

- Keep services in bounded contexts: `services/<name>/public/` and `services/<name>/internal/`.
- Keep staged RAG ingestion work isolated under `services/rag/internal/ingestion/`; parsing, semantic chunking, graph maps, and vector persistence logic must stay in separate modules.
- Add a new bounded context by creating its `public/` and `internal/` directories with `contracts.py`, `models.py`, `errors.py`, and `ports.py`.
- Wire new services in `config/container.py` only.
- Expose new routes by adding a sub-router and including it in `routes/api_router.py`.

## Verification

- Syntax: `python -m compileall assessment_app -q` from `app/backend/`.
- Import boundaries (no infra in services): `grep -r "from assessment_app.infra" assessment_app/services/` must return empty.
- Import boundaries (no internals in routes): `grep -r "from assessment_app.services.*internal" assessment_app/routes/` must return empty.
- Tests: `pytest tests/ -v` from `app/backend/` — all must pass.
