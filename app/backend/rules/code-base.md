I grounded the FastAPI-specific rules on FastAPI’s native dependency injection, router grouping, lifespan startup/shutdown, exception handling, and dependency overrides for tests; Pydantic’s model validation behavior; Chroma’s Python client modes; and Python’s official `sqlite3` docs. ([FastAPI][1])

# FastAPI + Python + REST + ChromaDB + SQLite Architecture Rules

## 0. Core Rule

This codebase follows **Contract-First Modular Architecture**.

Every module communicates through **interfaces/contracts**, not concrete classes.

Concrete implementations exist, but they are hidden behind contracts and wired only in the central dependency injection layer.

---

# A. Top-Level Directory Structure

```txt
project/
├── app/
│   ├── main.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── api_router.py
│   │   ├── health_routes.py
│   │   └── document_routes.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── documents/
│   │   │   ├── __init__.py
│   │   │   ├── public/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── contracts.py
│   │   │   │   ├── models.py
│   │   │   │   └── errors.py
│   │   │   └── internal/
│   │   │       ├── __init__.py
│   │   │       ├── service_impl.py
│   │   │       ├── repositories.py
│   │   │       ├── mappers.py
│   │   │       └── policies.py
│   │   │
│   │   └── chat/
│   │       ├── __init__.py
│   │       ├── public/
│   │       │   ├── __init__.py
│   │       │   ├── contracts.py
│   │       │   ├── models.py
│   │       │   └── errors.py
│   │       └── internal/
│   │           ├── __init__.py
│   │           ├── service_impl.py
│   │           ├── mappers.py
│   │           └── policies.py
│   │
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── sqlite/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py
│   │   │   ├── migrations.py
│   │   │   └── document_repository_sqlite.py
│   │   │
│   │   ├── chroma/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   └── document_vector_store_chroma.py
│   │   │
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── embedding_client.py
│   │   │   └── mock_embedding_client.py
│   │   │
│   │   └── observability/
│   │       ├── __init__.py
│   │       └── logging.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── container.py
│   │   ├── dependencies.py
│   │   └── exception_handlers.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── ids.py
│       ├── time.py
│       ├── pagination.py
│       └── text.py
│
├── tests/
│   ├── unit/
│   │   └── services/
│   │       └── documents/
│   │           └── test_document_service.py
│   ├── integration/
│   │   └── infra/
│   │       └── sqlite/
│   │           └── test_document_repository_sqlite.py
│   └── api/
│       └── test_document_routes.py
│
├── pyproject.toml
├── .env.example
└── README.md
```

---

# B. Python Naming Conventions

## Files and Modules

Use `snake_case`.

```txt
document_routes.py
service_impl.py
document_repository_sqlite.py
document_vector_store_chroma.py
```

## Classes

Use `PascalCase`.

```py
DocumentService
DefaultDocumentService
SqliteDocumentRepository
ChromaDocumentVectorStore
```

## Functions and Variables

Use `snake_case`.

```py
create_document()
get_document_service()
document_repository
```

## Interfaces / Contracts

Preferred Python style:

```py
class DocumentService(Protocol):
    ...
```

Do **not** use Java-style `IDocumentService` unless the team explicitly wants that convention.

Use:

```py
DocumentService
DocumentRepository
DocumentVectorStore
EmbeddingClient
```

Not:

```py
IDocumentService
IDocumentRepository
```

## Implementations

Use descriptive concrete names:

```py
DefaultDocumentService
SqliteDocumentRepository
InMemoryDocumentRepository
ChromaDocumentVectorStore
MockDocumentVectorStore
OpenAIEmbeddingClient
MockEmbeddingClient
```

Avoid vague names like:

```py
DocumentServiceImpl
RepositoryImpl
Manager
Helper
```

---

# C. Architectural Dependency Direction

The dependency direction is:

```txt
routes
  ↓
services/public contracts
  ↓
services/internal implementation
  ↓
service-defined repository contracts
  ↑
infra implementations
```

More practically:

```txt
routes ---------------> services/<module>/public
config ---------------> routes + services/internal + infra
services/internal ----> own public contracts
services/internal ----> other services' public contracts only
infra ----------------> services/<module>/public contracts
utils ----------------> no business imports
```

## The Composition Root

Only `config/container.py` is allowed to know concrete implementations.

That means this file is allowed to import:

```py
from app.services.documents.internal.service_impl import DefaultDocumentService
from app.infra.sqlite.document_repository_sqlite import SqliteDocumentRepository
from app.infra.chroma.document_vector_store_chroma import ChromaDocumentVectorStore
```

Everywhere else must use contracts.

---

# D. Service Structure

Each bounded context goes under:

```txt
app/services/<service_name>/
```

Example:

```txt
app/services/documents/
├── public/
│   ├── contracts.py
│   ├── models.py
│   └── errors.py
└── internal/
    ├── service_impl.py
    ├── repositories.py
    ├── mappers.py
    └── policies.py
```

## `public/`

This is the only part other modules may import.

It contains:

```txt
contracts.py   # service interfaces and public ports
models.py      # public DTOs and domain-facing models
errors.py      # service-level exceptions
```

## `internal/`

This is private implementation detail.

Other services must not import this.

It contains:

```txt
service_impl.py      # business logic implementation
repositories.py      # repository contracts owned by this service
mappers.py           # conversion helpers
policies.py          # business rule checks
```

---

# E. Service Public Contracts Example

File:

```txt
app/services/documents/public/contracts.py
```

```py
from typing import Protocol
from app.services.documents.public.models import (
    CreateDocumentCommand,
    DocumentView,
    SearchDocumentsQuery,
    SearchResult,
)


class DocumentService(Protocol):
    async def create_document(self, command: CreateDocumentCommand) -> DocumentView:
        ...

    async def get_document(self, document_id: str) -> DocumentView:
        ...

    async def search_documents(self, query: SearchDocumentsQuery) -> list[SearchResult]:
        ...


class DocumentSearchService(Protocol):
    async def search_documents(self, query: SearchDocumentsQuery) -> list[SearchResult]:
        ...
```

Why split `DocumentService` and `DocumentSearchService`?

Because another service may only need search, not full document management.

This keeps contracts smaller and avoids unnecessary coupling.

---

# F. Service Public Models Example

File:

```txt
app/services/documents/public/models.py
```

```py
from pydantic import BaseModel, Field


class CreateDocumentCommand(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class DocumentView(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str]


class SearchDocumentsQuery(BaseModel):
    text: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    document_id: str
    title: str
    score: float
```

Rules:

* Public models are safe to cross module boundaries.
* They are not database rows.
* They are not Chroma records.
* They are not HTTP request models unless intentionally reused.
* They represent the public contract of the service.

---

# G. Service Errors Example

File:

```txt
app/services/documents/public/errors.py
```

```py
class DocumentError(Exception):
    """Base error for the documents service."""


class DocumentNotFoundError(DocumentError):
    def __init__(self, document_id: str):
        self.document_id = document_id
        super().__init__(f"Document not found: {document_id}")


class DocumentAlreadyExistsError(DocumentError):
    pass


class DocumentValidationError(DocumentError):
    pass
```

Rules:

* Services raise service-level exceptions.
* Services do not raise `HTTPException`.
* Routes or global exception handlers convert service exceptions to HTTP responses.
* Infra errors should be wrapped into service-safe errors before crossing the service boundary.

---

# H. Repository Contracts

Repository contracts belong to the service that owns the data.

File:

```txt
app/services/documents/internal/repositories.py
```

```py
from typing import Protocol
from app.services.documents.public.models import DocumentView, SearchResult


class DocumentRepository(Protocol):
    async def save(self, document: DocumentView) -> None:
        ...

    async def find_by_id(self, document_id: str) -> DocumentView | None:
        ...

    async def delete(self, document_id: str) -> None:
        ...


class DocumentVectorStore(Protocol):
    async def index_document(self, document: DocumentView) -> None:
        ...

    async def search(self, text: str, limit: int) -> list[SearchResult]:
        ...
```

Important rule:

The repository interface is owned by the service, not by infra.

Why?

Because the service defines what it needs.

Infra only provides an implementation.

---

# I. Service Implementation Example

File:

```txt
app/services/documents/internal/service_impl.py
```

```py
from app.services.documents.internal.repositories import (
    DocumentRepository,
    DocumentVectorStore,
)
from app.services.documents.public.contracts import DocumentService
from app.services.documents.public.errors import DocumentNotFoundError
from app.services.documents.public.models import (
    CreateDocumentCommand,
    DocumentView,
    SearchDocumentsQuery,
    SearchResult,
)
from app.utils.ids import new_id


class DefaultDocumentService(DocumentService):
    def __init__(
        self,
        document_repository: DocumentRepository,
        vector_store: DocumentVectorStore,
    ) -> None:
        self._document_repository = document_repository
        self._vector_store = vector_store

    async def create_document(self, command: CreateDocumentCommand) -> DocumentView:
        document = DocumentView(
            id=new_id(),
            title=command.title,
            content=command.content,
            tags=command.tags,
        )

        await self._document_repository.save(document)
        await self._vector_store.index_document(document)

        return document

    async def get_document(self, document_id: str) -> DocumentView:
        document = await self._document_repository.find_by_id(document_id)

        if document is None:
            raise DocumentNotFoundError(document_id)

        return document

    async def search_documents(self, query: SearchDocumentsQuery) -> list[SearchResult]:
        return await self._vector_store.search(
            text=query.text,
            limit=query.limit,
        )
```

Rules:

* Service depends on repository/vector-store contracts.
* Service does not know SQLite.
* Service does not know ChromaDB.
* Service does not know FastAPI.
* Service does not know HTTP status codes.
* Service does not instantiate dependencies inline.

Forbidden:

```py
class DefaultDocumentService:
    def __init__(self):
        self.db = sqlite3.connect("app.db")
        self.chroma = chromadb.PersistentClient(path="./chroma")
```

Correct:

```py
class DefaultDocumentService:
    def __init__(self, document_repository: DocumentRepository, vector_store: DocumentVectorStore):
        self._document_repository = document_repository
        self._vector_store = vector_store
```

---

# J. Infra Layer

The infra layer contains concrete technical adapters.

Examples:

```txt
infra/sqlite/
infra/chroma/
infra/ai/
infra/observability/
```

Infra can implement service-defined interfaces.

Infra must not contain business orchestration.

Infra must not expose raw technical details into routes.

---

## SQLite Infra Structure

```txt
app/infra/sqlite/
├── connection.py
├── migrations.py
└── document_repository_sqlite.py
```

### `connection.py`

```py
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from app.config.settings import Settings


class SqliteConnectionFactory:
    def __init__(self, settings: Settings) -> None:
        self._database_url = settings.sqlite_database_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_url)
        connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
```

For a simple app, this factory is enough.

For heavier concurrency, prefer `aiosqlite`, SQLAlchemy async, or move to PostgreSQL.

---

## SQLite Repository Implementation

File:

```txt
app/infra/sqlite/document_repository_sqlite.py
```

```py
import json
from app.infra.sqlite.connection import SqliteConnectionFactory
from app.services.documents.internal.repositories import DocumentRepository
from app.services.documents.public.models import DocumentView


class SqliteDocumentRepository(DocumentRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    async def save(self, document: DocumentView) -> None:
        with self._connection_factory.connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (id, title, content, tags)
                VALUES (?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.title,
                    document.content,
                    json.dumps(document.tags),
                ),
            )

    async def find_by_id(self, document_id: str) -> DocumentView | None:
        with self._connection_factory.connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, content, tags
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()

        if row is None:
            return None

        return DocumentView(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            tags=json.loads(row["tags"]),
        )

    async def delete(self, document_id: str) -> None:
        with self._connection_factory.connect() as connection:
            connection.execute(
                """
                DELETE FROM documents
                WHERE id = ?
                """,
                (document_id,),
            )
```

Important SQLite rules:

* Use parameterized queries.
* Never build SQL with string interpolation.
* Do not return raw SQLite rows outside infra.
* Convert infra records into public service models or internal domain models.
* Keep schema creation/migrations outside repositories.

---

## Chroma Infra Structure

```txt
app/infra/chroma/
├── client.py
└── document_vector_store_chroma.py
```

### `client.py`

```py
import chromadb
from app.config.settings import Settings


class ChromaClientFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_client(self):
        return chromadb.PersistentClient(
            path=self._settings.chroma_path,
        )
```

### Chroma Vector Store Implementation

File:

```txt
app/infra/chroma/document_vector_store_chroma.py
```

```py
from app.services.documents.internal.repositories import DocumentVectorStore
from app.services.documents.public.models import DocumentView, SearchResult


class ChromaDocumentVectorStore(DocumentVectorStore):
    def __init__(self, chroma_client) -> None:
        self._collection = chroma_client.get_or_create_collection(
            name="documents",
        )

    async def index_document(self, document: DocumentView) -> None:
        self._collection.upsert(
            ids=[document.id],
            documents=[document.content],
            metadatas=[
                {
                    "title": document.title,
                    "tags": ",".join(document.tags),
                }
            ],
        )

    async def search(self, text: str, limit: int) -> list[SearchResult]:
        result = self._collection.query(
            query_texts=[text],
            n_results=limit,
        )

        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]

        search_results: list[SearchResult] = []

        for document_id, distance, metadata in zip(ids, distances, metadatas):
            score = 1.0 - float(distance)

            search_results.append(
                SearchResult(
                    document_id=document_id,
                    title=str(metadata.get("title", "")),
                    score=score,
                )
            )

        return search_results
```

Rules:

* Chroma code lives in infra.
* Services only depend on `DocumentVectorStore`.
* Chroma collection names must be defined centrally or passed from settings.
* Do not leak raw Chroma query result dictionaries into services.
* Convert raw vector DB output into public service models.

---

# K. Routes / Controllers Layer

Routes live in:

```txt
app/routes/
```

Routes are responsible for:

* HTTP request parsing
* HTTP response formatting
* HTTP status codes
* Calling services through interfaces
* Authentication/authorization dependencies
* Mapping HTTP models to service commands

Routes are not responsible for:

* Business rules
* SQL
* Chroma calls
* Creating service implementations
* Cross-service orchestration

---

## Route Structure

```txt
app/routes/
├── api_router.py
├── document_routes.py
├── chat_routes.py
└── health_routes.py
```

### `api_router.py`

```py
from fastapi import APIRouter
from app.routes.document_routes import router as document_router
from app.routes.health_routes import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(document_router, prefix="/documents", tags=["documents"])
```

---

## Route DTOs

You can place route-specific DTOs inside the route file for small modules.

For larger modules, create:

```txt
app/routes/dtos/document_dtos.py
```

Example inside `document_routes.py`:

```py
from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str]
```

Rule:

HTTP DTOs are allowed to differ from service models.

Why?

Because HTTP shape and business shape often evolve differently.

---

## Route Example

File:

```txt
app/routes/document_routes.py
```

```py
from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.config.dependencies import get_document_service
from app.services.documents.public.contracts import DocumentService
from app.services.documents.public.models import (
    CreateDocumentCommand,
    SearchDocumentsQuery,
)
from pydantic import BaseModel, Field


router = APIRouter()


class CreateDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str]


class SearchDocumentResponse(BaseModel):
    document_id: str
    title: str
    score: float


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    request: CreateDocumentRequest,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    document = await document_service.create_document(
        CreateDocumentCommand(
            title=request.title,
            content=request.content,
            tags=request.tags,
        )
    )

    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        tags=document.tags,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    document = await document_service.get_document(document_id)

    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        tags=document.tags,
    )


@router.get("/search/", response_model=list[SearchDocumentResponse])
async def search_documents(
    text: str,
    limit: int = 10,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
) -> list[SearchDocumentResponse]:
    results = await document_service.search_documents(
        SearchDocumentsQuery(text=text, limit=limit)
    )

    return [
        SearchDocumentResponse(
            document_id=item.document_id,
            title=item.title,
            score=item.score,
        )
        for item in results
    ]
```

Important:

Routes depend on service contracts.

Correct:

```py
from app.services.documents.public.contracts import DocumentService
```

Wrong:

```py
from app.services.documents.internal.service_impl import DefaultDocumentService
from app.infra.sqlite.document_repository_sqlite import SqliteDocumentRepository
```

---

# L. Dependency Injection Setup

FastAPI’s standard approach is dependency functions using `Depends`.

For this architecture:

* Use FastAPI `Depends` at the route/controller boundary.
* Use constructor injection inside services.
* Use a central container to build concrete implementations.
* Store the container in `app.state.container`.
* Never instantiate concrete dependencies inside route functions or service methods.

---

## Settings

File:

```txt
app/config/settings.py
```

```py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Contract First FastAPI App"
    environment: str = "dev"

    sqlite_database_path: str = "data/app.sqlite3"
    chroma_path: str = "data/chroma"

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
```

---

## Container

File:

```txt
app/config/container.py
```

```py
from dataclasses import dataclass

from app.config.settings import Settings
from app.infra.chroma.client import ChromaClientFactory
from app.infra.chroma.document_vector_store_chroma import ChromaDocumentVectorStore
from app.infra.sqlite.connection import SqliteConnectionFactory
from app.infra.sqlite.document_repository_sqlite import SqliteDocumentRepository
from app.services.documents.public.contracts import DocumentService
from app.services.documents.internal.service_impl import DefaultDocumentService


@dataclass(frozen=True)
class AppContainer:
    document_service: DocumentService


def build_container(settings: Settings) -> AppContainer:
    sqlite_connection_factory = SqliteConnectionFactory(settings=settings)

    document_repository = SqliteDocumentRepository(
        connection_factory=sqlite_connection_factory,
    )

    chroma_client = ChromaClientFactory(settings=settings).create_client()

    document_vector_store = ChromaDocumentVectorStore(
        chroma_client=chroma_client,
    )

    document_service = DefaultDocumentService(
        document_repository=document_repository,
        vector_store=document_vector_store,
    )

    return AppContainer(
        document_service=document_service,
    )
```

Rules:

* `build_container()` is the composition root.
* Concrete classes are imported here.
* Services receive dependencies through constructors.
* Routes receive services through FastAPI dependencies.
* Test containers can replace implementations.

---

## FastAPI Dependency Providers

File:

```txt
app/config/dependencies.py
```

```py
from fastapi import Request

from app.config.container import AppContainer
from app.services.documents.public.contracts import DocumentService


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_document_service(request: Request) -> DocumentService:
    container = get_container(request)
    return container.document_service
```

Rules:

* Dependency providers should be thin.
* They should only retrieve already-wired dependencies.
* They should not build implementations repeatedly.
* They should not contain business logic.

---

## Application Factory

File:

```txt
app/main.py
```

```py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config.container import build_container
from app.config.exception_handlers import register_exception_handlers
from app.config.settings import Settings
from app.infra.sqlite.migrations import run_migrations
from app.routes.api_router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()

    run_migrations(settings)

    app.state.container = build_container(settings)

    yield

    # Close long-lived external clients here if needed.


def create_app() -> FastAPI:
    app = FastAPI(
        title="Contract First FastAPI App",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
```

---

# M. Swapping Implementations

## Dev

```py
document_repository = SqliteDocumentRepository(...)
document_vector_store = ChromaDocumentVectorStore(...)
```

## Test

```py
document_repository = InMemoryDocumentRepository()
document_vector_store = FakeDocumentVectorStore()
```

## Production

```py
document_repository = SqliteDocumentRepository(...)
document_vector_store = ChromaDocumentVectorStore(...)
```

Or later:

```py
document_repository = PostgresDocumentRepository(...)
document_vector_store = ChromaCloudDocumentVectorStore(...)
```

No service code changes.

Only `config/container.py` changes.

---

# N. In-Memory Test Implementations

File:

```txt
tests/fakes/in_memory_document_repository.py
```

```py
from app.services.documents.internal.repositories import DocumentRepository
from app.services.documents.public.models import DocumentView


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self) -> None:
        self._documents: dict[str, DocumentView] = {}

    async def save(self, document: DocumentView) -> None:
        self._documents[document.id] = document

    async def find_by_id(self, document_id: str) -> DocumentView | None:
        return self._documents.get(document_id)

    async def delete(self, document_id: str) -> None:
        self._documents.pop(document_id, None)
```

File:

```txt
tests/fakes/fake_document_vector_store.py
```

```py
from app.services.documents.internal.repositories import DocumentVectorStore
from app.services.documents.public.models import DocumentView, SearchResult


class FakeDocumentVectorStore(DocumentVectorStore):
    def __init__(self) -> None:
        self.indexed: list[DocumentView] = []

    async def index_document(self, document: DocumentView) -> None:
        self.indexed.append(document)

    async def search(self, text: str, limit: int) -> list[SearchResult]:
        return [
            SearchResult(
                document_id=document.id,
                title=document.title,
                score=1.0,
            )
            for document in self.indexed[:limit]
            if text.lower() in document.content.lower()
        ]
```

---

# O. Error Handling Strategy

## Exception Flow

```txt
infra error
   ↓
repository wraps or re-raises meaningful service-safe error
   ↓
service raises public service exception
   ↓
FastAPI exception handler maps to HTTP response
```

## Rules

Services do not raise `HTTPException`.

Infra does not raise `HTTPException`.

Only routes or exception handlers understand HTTP status codes.

---

## Global Exception Handler

File:

```txt
app/config/exception_handlers.py
```

```py
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.documents.public.errors import (
    DocumentError,
    DocumentNotFoundError,
    DocumentValidationError,
)


logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DocumentNotFoundError)
    async def handle_document_not_found(
        request: Request,
        exc: DocumentNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "DOCUMENT_NOT_FOUND",
                "message": str(exc),
            },
        )

    @app.exception_handler(DocumentValidationError)
    async def handle_document_validation_error(
        request: Request,
        exc: DocumentValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "DOCUMENT_VALIDATION_ERROR",
                "message": str(exc),
            },
        )

    @app.exception_handler(DocumentError)
    async def handle_document_error(
        request: Request,
        exc: DocumentError,
    ) -> JSONResponse:
        logger.warning("Document service error: %s", exc)

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "DOCUMENT_ERROR",
                "message": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unexpected server error")

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
            },
        )
```

---

# P. Validation Strategy

## HTTP Validation

Use Pydantic request DTOs.

Example:

```py
class CreateDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
```

This validates request shape.

## Business Rule Validation

Put business validation in services or service policies.

Example:

```py
class DocumentPolicy:
    def ensure_can_create(self, title: str, content: str) -> None:
        if title.lower() == "admin":
            raise DocumentValidationError("Document title cannot be 'admin'.")
```

## Database Validation

Use database constraints for final consistency.

Examples:

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL
);
```

## Rule

Do not rely on only one validation layer.

Use:

```txt
Pydantic DTO validation
+ service business validation
+ DB constraints
```

---

# Q. Async Patterns

FastAPI supports async endpoints.

Recommended rules for this stack:

## Routes

Use `async def`.

```py
@router.post("")
async def create_document(...):
    ...
```

## Services

Use `async def` when they call async dependencies or may later call async dependencies.

```py
class DocumentService(Protocol):
    async def create_document(self, command: CreateDocumentCommand) -> DocumentView:
        ...
```

## Repositories

Use `async def` in contracts even if SQLite implementation is internally sync.

Why?

Because it keeps contracts future-proof for:

* PostgreSQL async driver
* network calls
* Chroma server
* cloud vector DB
* message queues

## SQLite Warning

The built-in `sqlite3` module is synchronous.

For a small app, this is acceptable.

For higher concurrency, use:

* `aiosqlite`
* SQLAlchemy async
* PostgreSQL with async driver

## Do Not Mix Randomly

Avoid:

```py
def service_method():
    await something()
```

Avoid:

```py
async def service_method():
    time.sleep(5)
```

Use:

```py
await asyncio.sleep(5)
```

or offload blocking work properly.

---

# R. Utils Layer

`utils/` contains dependency-free helpers only.

Allowed:

```txt
utils/ids.py
utils/time.py
utils/text.py
utils/pagination.py
```

Example:

```py
import uuid


def new_id() -> str:
    return str(uuid.uuid4())
```

Allowed utils:

* ID generation
* Date/time helpers
* Text normalization
* Pagination helpers
* Pure validation helpers
* Serialization helpers with no business dependency

Forbidden in utils:

* Business rules
* Repositories
* Database connections
* Chroma clients
* FastAPI route dependencies
* Service calls
* Anything importing from `services/*/internal`
* Anything importing from `infra`

Wrong:

```py
# utils/document_helper.py
from app.infra.sqlite.document_repository_sqlite import SqliteDocumentRepository
```

Correct:

```py
# utils/text.py
def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())
```

---

# S. Testing Strategy

## Test Directory

```txt
tests/
├── unit/
│   └── services/
├── integration/
│   └── infra/
└── api/
    └── routes/
```

## Unit Tests

Test services with fake repositories.

```py
import pytest

from app.services.documents.internal.service_impl import DefaultDocumentService
from app.services.documents.public.models import CreateDocumentCommand
from tests.fakes.in_memory_document_repository import InMemoryDocumentRepository
from tests.fakes.fake_document_vector_store import FakeDocumentVectorStore


@pytest.mark.asyncio
async def test_create_document_indexes_document():
    repository = InMemoryDocumentRepository()
    vector_store = FakeDocumentVectorStore()

    service = DefaultDocumentService(
        document_repository=repository,
        vector_store=vector_store,
    )

    document = await service.create_document(
        CreateDocumentCommand(
            title="Test",
            content="Hello world",
            tags=["demo"],
        )
    )

    saved = await repository.find_by_id(document.id)

    assert saved is not None
    assert saved.title == "Test"
    assert len(vector_store.indexed) == 1
```

## API Tests with Dependency Override

```py
from fastapi.testclient import TestClient

from app.main import create_app
from app.config.dependencies import get_document_service
from app.services.documents.public.contracts import DocumentService


class FakeDocumentService(DocumentService):
    async def create_document(self, command):
        return {
            "id": "doc_1",
            "title": command.title,
            "content": command.content,
            "tags": command.tags,
        }


def test_create_document_route():
    app = create_app()

    async def override_document_service():
        return FakeDocumentService()

    app.dependency_overrides[get_document_service] = override_document_service

    client = TestClient(app)

    response = client.post(
        "/api/v1/documents",
        json={
            "title": "Hello",
            "content": "World",
            "tags": [],
        },
    )

    assert response.status_code == 201
```

## Integration Tests

Use real SQLite with temporary DB.

Use fake Chroma if the test is only for SQLite.

Use real Chroma only in vector-store integration tests.

---

# T. Cross-Module Communication Rules

## What Service A Can Import From Service B

Allowed:

```py
from app.services.documents.public.contracts import DocumentSearchService
from app.services.documents.public.models import SearchDocumentsQuery
```

Forbidden:

```py
from app.services.documents.internal.service_impl import DefaultDocumentService
from app.services.documents.internal.repositories import DocumentRepository
from app.infra.chroma.document_vector_store_chroma import ChromaDocumentVectorStore
```

## What Routes Can Import

Allowed:

```py
from app.services.documents.public.contracts import DocumentService
from app.services.documents.public.models import CreateDocumentCommand
```

Forbidden:

```py
from app.services.documents.internal.service_impl import DefaultDocumentService
from app.infra.sqlite.document_repository_sqlite import SqliteDocumentRepository
```

## What Infra Can Import

Allowed:

```py
from app.services.documents.internal.repositories import DocumentRepository
```

This is allowed because infra implements the service-owned port.

Forbidden:

```py
from app.routes.document_routes import CreateDocumentRequest
```

Infra must not depend on routes.

## What Utils Can Import

Allowed:

```py
import uuid
from datetime import datetime
```

Forbidden:

```py
from app.services.documents.public.contracts import DocumentService
from app.infra.sqlite.connection import SqliteConnectionFactory
```

---

# U. Correct vs Wrong Import Examples

## Correct Route

```py
from app.services.documents.public.contracts import DocumentService
from app.config.dependencies import get_document_service
```

## Wrong Route

```py
from app.services.documents.internal.service_impl import DefaultDocumentService
```

Why wrong?

The route is now coupled to implementation.

---

## Correct Service-to-Service Communication

```py
from app.services.documents.public.contracts import DocumentSearchService
```

## Wrong Service-to-Service Communication

```py
from app.services.documents.internal.service_impl import DefaultDocumentService
```

Why wrong?

It breaks bounded context isolation.

---

## Correct Infra Implementation

```py
from app.services.documents.internal.repositories import DocumentRepository
```

## Wrong Infra Implementation

```py
from app.routes.document_routes import CreateDocumentRequest
```

Why wrong?

Infra should never know HTTP DTOs.

---

# V. Code Example: New Service End-to-End

Example new bounded context:

```txt
chat
```

Goal:

The chat service answers questions using document search.

---

## 1. Public Models

File:

```txt
app/services/chat/public/models.py
```

```py
from pydantic import BaseModel, Field


class AskQuestionCommand(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class AnswerView(BaseModel):
    answer: str
    sources: list[str]
```

---

## 2. Public Contract

File:

```txt
app/services/chat/public/contracts.py
```

```py
from typing import Protocol

from app.services.chat.public.models import AskQuestionCommand, AnswerView


class ChatService(Protocol):
    async def ask(self, command: AskQuestionCommand) -> AnswerView:
        ...
```

---

## 3. AI Client Port

File:

```txt
app/services/chat/internal/ai_ports.py
```

```py
from typing import Protocol


class AnswerGenerator(Protocol):
    async def generate_answer(self, question: str, context: list[str]) -> str:
        ...
```

---

## 4. Service Implementation

File:

```txt
app/services/chat/internal/service_impl.py
```

```py
from app.services.chat.internal.ai_ports import AnswerGenerator
from app.services.chat.public.contracts import ChatService
from app.services.chat.public.models import AskQuestionCommand, AnswerView
from app.services.documents.public.contracts import DocumentSearchService
from app.services.documents.public.models import SearchDocumentsQuery


class DefaultChatService(ChatService):
    def __init__(
        self,
        document_search_service: DocumentSearchService,
        answer_generator: AnswerGenerator,
    ) -> None:
        self._document_search_service = document_search_service
        self._answer_generator = answer_generator

    async def ask(self, command: AskQuestionCommand) -> AnswerView:
        search_results = await self._document_search_service.search_documents(
            SearchDocumentsQuery(
                text=command.question,
                limit=command.limit,
            )
        )

        context = [result.title for result in search_results]

        answer = await self._answer_generator.generate_answer(
            question=command.question,
            context=context,
        )

        return AnswerView(
            answer=answer,
            sources=[result.document_id for result in search_results],
        )
```

Important:

The chat service depends on `DocumentSearchService`, not `DefaultDocumentService`.

---

## 5. Infra AI Implementation

File:

```txt
app/infra/ai/simple_answer_generator.py
```

```py
from app.services.chat.internal.ai_ports import AnswerGenerator


class SimpleAnswerGenerator(AnswerGenerator):
    async def generate_answer(self, question: str, context: list[str]) -> str:
        joined_context = "\n".join(context)

        return (
            f"Question: {question}\n\n"
            f"Based on these sources:\n{joined_context}"
        )
```

---

## 6. Route

File:

```txt
app/routes/chat_routes.py
```

```py
from typing import Annotated
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config.dependencies import get_chat_service
from app.services.chat.public.contracts import ChatService
from app.services.chat.public.models import AskQuestionCommand


router = APIRouter()


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class AskQuestionResponse(BaseModel):
    answer: str
    sources: list[str]


@router.post("/ask", response_model=AskQuestionResponse)
async def ask_question(
    request: AskQuestionRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> AskQuestionResponse:
    answer = await chat_service.ask(
        AskQuestionCommand(
            question=request.question,
            limit=request.limit,
        )
    )

    return AskQuestionResponse(
        answer=answer.answer,
        sources=answer.sources,
    )
```

---

## 7. DI Wiring

File:

```txt
app/config/container.py
```

```py
from dataclasses import dataclass

from app.config.settings import Settings
from app.infra.ai.simple_answer_generator import SimpleAnswerGenerator
from app.infra.chroma.client import ChromaClientFactory
from app.infra.chroma.document_vector_store_chroma import ChromaDocumentVectorStore
from app.infra.sqlite.connection import SqliteConnectionFactory
from app.infra.sqlite.document_repository_sqlite import SqliteDocumentRepository
from app.services.chat.public.contracts import ChatService
from app.services.chat.internal.service_impl import DefaultChatService
from app.services.documents.public.contracts import DocumentService
from app.services.documents.internal.service_impl import DefaultDocumentService


@dataclass(frozen=True)
class AppContainer:
    document_service: DocumentService
    chat_service: ChatService


def build_container(settings: Settings) -> AppContainer:
    sqlite_connection_factory = SqliteConnectionFactory(settings=settings)

    document_repository = SqliteDocumentRepository(
        connection_factory=sqlite_connection_factory,
    )

    chroma_client = ChromaClientFactory(settings=settings).create_client()

    document_vector_store = ChromaDocumentVectorStore(
        chroma_client=chroma_client,
    )

    document_service = DefaultDocumentService(
        document_repository=document_repository,
        vector_store=document_vector_store,
    )

    answer_generator = SimpleAnswerGenerator()

    chat_service = DefaultChatService(
        document_search_service=document_service,
        answer_generator=answer_generator,
    )

    return AppContainer(
        document_service=document_service,
        chat_service=chat_service,
    )
```

File:

```txt
app/config/dependencies.py
```

```py
from fastapi import Request

from app.config.container import AppContainer
from app.services.chat.public.contracts import ChatService
from app.services.documents.public.contracts import DocumentService


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_document_service(request: Request) -> DocumentService:
    return get_container(request).document_service


def get_chat_service(request: Request) -> ChatService:
    return get_container(request).chat_service
```

---

# W. Multiple Implementation Naming Strategy

## Services

```txt
DefaultDocumentService
CachedDocumentService
InstrumentedDocumentService
```

## Repositories

```txt
SqliteDocumentRepository
PostgresDocumentRepository
InMemoryDocumentRepository
```

## Vector Stores

```txt
ChromaDocumentVectorStore
InMemoryDocumentVectorStore
MockDocumentVectorStore
```

## AI Clients

```txt
OpenAIAnswerGenerator
LocalAnswerGenerator
MockAnswerGenerator
SimpleAnswerGenerator
```

## When To Create Multiple Implementations

Create multiple implementations when:

* You need a test fake.
* You need dev/prod behavior.
* You are switching storage engines.
* You need a feature flag.
* You need a mock external API.
* You need an in-memory mode for local development.

Do not create multiple implementations just because “architecture says so.”

---

# X. Logging and Observability

## Rules

* Configure logging in `infra/observability/logging.py`.
* Services log important business events.
* Infra logs technical failures.
* Exception handlers log unexpected errors.
* Do not log secrets.
* Do not log full embeddings.
* Do not log full user documents unless explicitly safe.
* Include request IDs if available.

Example:

```py
import logging

logger = logging.getLogger(__name__)


class DefaultDocumentService:
    async def create_document(self, command):
        logger.info("Creating document with title=%s", command.title)
        ...
```

For production, prefer structured JSON logging.

---

# Y. Documentation and Comments

## Docstrings

Use docstrings for public contracts.

```py
class DocumentService(Protocol):
    """Public contract for document management operations."""

    async def create_document(self, command: CreateDocumentCommand) -> DocumentView:
        """Create and index a document."""
```

## What To Document

Document:

* Public contracts
* Business rules
* Non-obvious decisions
* Error behavior
* Side effects
* External API assumptions
* Data consistency assumptions

Do not document obvious Python syntax.

Bad:

```py
# Increment i by 1
i += 1
```

Good:

```py
# Indexing happens after SQLite save so search never returns unsaved documents.
await self._vector_store.index_document(document)
```

---

# Z. Checklist: Adding a New Service

When adding a new service:

* [ ] Create `app/services/<name>/public/`
* [ ] Create `contracts.py`
* [ ] Create `models.py`
* [ ] Create `errors.py`
* [ ] Create `app/services/<name>/internal/`
* [ ] Add `service_impl.py`
* [ ] Add repository/vector/API ports if needed
* [ ] Keep implementation dependencies interface-only
* [ ] Add infra adapters if needed
* [ ] Wire concrete implementations in `config/container.py`
* [ ] Add dependency provider in `config/dependencies.py`
* [ ] Add routes in `app/routes/<name>_routes.py`
* [ ] Include router in `api_router.py`
* [ ] Add unit tests with fakes
* [ ] Add API tests with dependency overrides
* [ ] Add integration tests for infra adapters
* [ ] Check import rules

---

# AA. Checklist: Adding a Listener / Event Handler

Even if the current app is REST-first, event handlers should follow the same rules.

Recommended structure:

```txt
app/infra/messaging/
├── consumer.py
├── publisher.py
└── handlers/
    └── document_created_handler.py
```

Rules:

* Listener lives in infra.
* Listener parses technical message format.
* Listener calls service interface.
* Listener does not contain business logic.
* Listener does not import service internals.
* Listener dependencies are wired in `config/container.py`.

Checklist:

* [ ] Define event model.
* [ ] Define service method/contract needed by the listener.
* [ ] Implement business logic in service.
* [ ] Create listener in infra.
* [ ] Inject service interface into listener.
* [ ] Register listener during startup/lifespan.
* [ ] Add retry/dead-letter strategy if using a real queue.
* [ ] Add idempotency if event can be delivered more than once.
* [ ] Add tests with fake service.

Example:

```py
class DocumentCreatedEventHandler:
    def __init__(self, document_service: DocumentService) -> None:
        self._document_service = document_service

    async def handle(self, payload: dict) -> None:
        await self._document_service.get_document(payload["document_id"])
```

---

# AB. Common Anti-Patterns and Fixes

## Anti-Pattern 1: Route Instantiates Service

Wrong:

```py
@router.post("")
async def create_document(request: CreateDocumentRequest):
    repo = SqliteDocumentRepository()
    service = DefaultDocumentService(repo)
    return await service.create_document(...)
```

Fix:

```py
@router.post("")
async def create_document(
    request: CreateDocumentRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    return await service.create_document(...)
```

---

## Anti-Pattern 2: Service Imports Concrete Infra

Wrong:

```py
from app.infra.chroma.document_vector_store_chroma import ChromaDocumentVectorStore
```

Fix:

```py
from app.services.documents.internal.repositories import DocumentVectorStore
```

---

## Anti-Pattern 3: Business Logic in Routes

Wrong:

```py
@router.post("")
async def create_document(request):
    if request.title == "admin":
        raise HTTPException(400)
```

Fix:

```py
class DocumentPolicy:
    def validate_title(self, title: str) -> None:
        if title == "admin":
            raise DocumentValidationError("Invalid title.")
```

---

## Anti-Pattern 4: Raw DB Rows Returned From Repository

Wrong:

```py
return row
```

Fix:

```py
return DocumentView(
    id=row["id"],
    title=row["title"],
    content=row["content"],
    tags=json.loads(row["tags"]),
)
```

---

## Anti-Pattern 5: Utils Become a Dumping Ground

Wrong:

```txt
utils/document_service_helper.py
utils/db_helper.py
utils/chroma_helper.py
```

Fix:

```txt
services/documents/internal/policies.py
infra/sqlite/connection.py
infra/chroma/client.py
```

---

## Anti-Pattern 6: Cross-Service Internal Imports

Wrong:

```py
from app.services.documents.internal.service_impl import DefaultDocumentService
```

Fix:

```py
from app.services.documents.public.contracts import DocumentSearchService
```

---

## Anti-Pattern 7: HTTP Exceptions Inside Services

Wrong:

```py
from fastapi import HTTPException

raise HTTPException(status_code=404)
```

Fix:

```py
raise DocumentNotFoundError(document_id)
```

Then map it in `exception_handlers.py`.

---

# AC. Final Architecture Rules Summary

## Always Do This

* Use contracts for cross-module communication.
* Keep `public/` and `internal/` separate.
* Inject dependencies through constructors.
* Bind concrete implementations in `config/container.py`.
* Use FastAPI `Depends` only at route/controller boundaries.
* Keep routes thin.
* Keep services business-focused.
* Keep repositories storage-focused.
* Keep infra technical.
* Keep utils dependency-free.
* Write tests against interfaces.

## Never Do This

* Do not import service internals from another service.
* Do not import concrete infra inside services.
* Do not instantiate dependencies inside business logic.
* Do not put business rules in routes.
* Do not return raw DB/vector DB records from infra.
* Do not let utils import services or infra.
* Do not raise `HTTPException` inside services.
* Do not make ChromaDB or SQLite visible to routes.
* Do not allow circular imports.
* Do not treat Pydantic HTTP DTOs as database models.

---

# AD. The Mental Model

Think of the system like this:

```txt
HTTP world
  |
  v
routes
  |
  v
service contracts
  |
  v
business services
  |
  v
repository/vector/AI contracts
  |
  v
infra implementations
  |
  v
SQLite / ChromaDB / External APIs
```

Only the DI container connects concrete pieces together.

Everything else talks through contracts.

[1]: https://fastapi.tiangolo.com/tutorial/dependencies/ "Dependencies - FastAPI"
