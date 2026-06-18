# Codebase Rule

## Core Principle

Code must be easy to read, easy to replace, and easy to extend.

Prefer boring, obvious structure over clever patterns. Keep every module small, focused, and named by responsibility.

## Project Shape

Organize application code by clear layers:

- `infra/` - external systems and concrete adapters: database, vector store, LLM clients, PDF loaders, environment config.
- `services/` - business workflows and orchestration: ingest flow, query flow, analytics flow.
- `routes/` - HTTP/API entrypoints only: request validation, response mapping, status codes.
- `utils/` - small shared helpers with no business ownership.
- `interfaces/` - contracts/ports used by services to avoid depending on concrete implementations.
- `models/` or `schemas/` - Pydantic/domain data shapes.

Routes must not contain business logic. Infra must not call routes. Services coordinate interfaces and domain flow.

## Interface-First Design

Use interfaces/protocols/abstract base classes for replaceable parts, similar to Spring-style dependency inversion.

Use interfaces for:

- PDF/document loading.
- Chunking.
- Embedding generation.
- Vector storage and retrieval.
- Chat/LLM generation.
- SQL logging.
- Analytics queries.
- RAG ingestion flow.
- RAG query flow.

Services depend on interfaces, not concrete classes.

Concrete implementations live in `infra/` and can be replaced without changing service logic.

Example rule:

```text
RagQueryService depends on VectorStore, ChatClient, QueryLogger interfaces.
RagQueryService must not know whether vector storage is Chroma, FAISS, Neo4j, or anything else.
```

## Keep It Stupidly Simple

- Prefer one clear class/function over multiple tiny abstractions when replaceability is not needed.
- Add abstraction only where implementation replacement is likely or already required.
- Avoid deep inheritance.
- Avoid hidden side effects.
- Avoid global mutable state.
- Avoid framework magic when simple dependency injection is enough.
- Prefer explicit constructor dependencies.

## RAG Ingest Flow Rule

The ingest flow must be modular and replaceable:

```text
document loader
-> hierarchical parser
-> semantic chunker
-> embedding client
-> graph builder
-> SQLite graph maps
-> Chroma vector index
```

Each step must have an interface.

The ingest service owns orchestration only. It must not directly parse PDFs, call model APIs, or write to Chroma/FAISS/Neo4j without going through interfaces.

## RAG Query Flow Rule

The query flow must be modular and replaceable:

```text
query validation
-> retrieval
-> prompt building
-> LLM answer generation
-> source packaging
-> SQL logging
-> response
```

Each replaceable dependency must sit behind an interface.

The query service owns orchestration only. It must not contain HTTP logic or concrete infrastructure code.

## Logging And Analytics Rule

Every user-facing query must be logged through a logging interface.

Analytics must be read through a separate analytics interface/service, not by routes directly querying SQL.

## Naming Rule

Names should reveal responsibility:

Good:
- `ChromaVectorStore`
- `OpenAICompatibleChatClient`
- `SqliteQueryLogger`
- `DefaultIngestionParsingService`
- `RagQueryService`
- `AnalyticsService`

Avoid:
- `Manager`
- `Helper`
- `Processor` unless responsibility is specific
- giant `utils.py` files

## Modularity Rule

A module should have one reason to change.

Examples:
- Changing from Chroma to FAISS should affect only vector-store implementation wiring.
- Changing from Ollama to NVIDIA/OpenAI should affect only chat/embedding clients and env config.
- Changing SQL schema should affect logging/analytics infra, not query route logic.
- Changing chunk size should affect ingestion chunking configuration, not API routes.

## Readability Rule

- Short functions.
- Explicit inputs and outputs.
- Type hints for public functions.
- Pydantic models for API boundaries.
- Small comments only where they explain why, not what.
- No large nested control flow when helper functions make flow clearer.

## Error Handling Rule

Handle errors at the right layer:

- Routes convert known service errors to HTTP responses.
- Services raise clear domain/application errors.
- Infra wraps external-system failures with readable messages.
- No raw stack traces should leak to API users.

## Testing Rule

Test by layer:

- Unit test services with fake interface implementations.
- Unit test infra adapters where practical.
- API test routes with dependency overrides.
- Keep at least one end-to-end smoke path for ingest, ask, and analytics.

## Final Project Standard

The final app must feel like a small clean production codebase, not a notebook or script collection.

It should be:
- readable
- loosely coupled
- modular
- extensible
- scalable in structure
- simple enough to explain in a walkthrough
