# Final Assessment App

## Purpose

- Owns the clean FastAPI and React implementation for the AWS Customer Agreement RAG assessment.
- Keeps final deliverable code and source materials self-contained under `app/`.

## Ownership

- `backend/` owns FastAPI routes, RAG services, concrete infrastructure adapters, SQL logging, analytics, and backend tests.
- `frontend/` owns the React chat, analytics, and evaluation UI.
- `resources/` owns app-local source PDFs used by final app ingestion.
- `evaluation/` owns durable docs for benchmark evaluation flow and metric categories.
- `README.md` owns final app setup, run, design, and demo instructions.
- `CODEBASE_EXPLAINED.md` owns the architecture walkthrough and codebase explanation for review/demo.
- `CODEBASE_RULE.md` owns app-local engineering and architecture rules.

## Local Contracts

- Follow `CODEBASE_RULE.md` for code organization, interface-first design, modularity, naming, and testing.
- Do not depend on code or source material outside `app/` for runtime RAG or query behavior.
- Keep final app source PDFs under `app/resources/`; do not depend on root `resources/`.
- Preserve the prototype-inspired query shape inside app code: section-aware ingest, semantic retrieval, evidence expansion, grounded answer, SQL logging.
- Evaluation benchmark runs must reuse the real query flow without polluting normal SQL analytics.
- Runtime data must stay under ignored backend data directories, not committed source.
- The final app must use `app/resources/AWS Customer Agreement.pdf` as its source document.

## Work Guidance

- Keep routes thin — no business logic.
- Organise services as bounded contexts: `services/<name>/public/` (contracts, models, errors) and `services/<name>/internal/` (implementation, ports).
- Put replaceable concrete dependencies in `backend/assessment_app/infra/<subsystem>/`.
- Put service contracts (Protocols) in each service's `public/contracts.py` — never in a top-level `interfaces/` directory.
- Wire concrete implementations only in `backend/assessment_app/config/container.py`.
- Route handlers receive services via FastAPI `Depends` using typed aliases from `config/dependencies.py`.
- Prefer explicit constructor injection over framework magic.

## Verification

- Backend syntax: `python -m compileall assessment_app` from `app/backend/`.
- Backend tests: `pytest` from `app/backend/` when dependencies are installed.
- Frontend build: `npm run build` from `app/frontend/` when dependencies are installed.

## Child DOX Index

- `resources/AGENTS.md` - App-local source PDFs bundled with the standalone final assessment app.
- `evaluation/AGENTS.md` - Durable query evaluation flow and metric documentation.
