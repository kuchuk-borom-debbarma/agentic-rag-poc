"""Application settings loaded from environment variables and .env file."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Immutable configuration for the assessment app.

    Loaded once at startup via load_settings() and stored on app.state.settings.
    """

    app_name: str
    pdf_path: Path
    chroma_dir: Path
    chroma_collection: str
    rag_chroma_collection: str
    sqlite_path: Path
    graph_sqlite_path: Path
    chunk_size: int
    chunk_overlap: int
    default_top_k: int
    default_neighbors: int
    embedding_base_url: str
    embedding_model: str
    embedding_api_key: str | None
    chat_base_url: str
    chat_model: str
    chat_api_key: str | None
    chat_max_tokens: int
    chat_temperature: float


def load_settings() -> Settings:
    """Load settings from environment variables, resolving paths relative to backend root."""
    backend_root = Path(__file__).resolve().parents[2]
    load_dotenv(backend_root / ".env")
    return Settings(
        app_name=os.getenv("APP_NAME", "AWS Customer Agreement RAG"),
        pdf_path=_resolve_path(os.getenv("PDF_PATH", "../resources/AWS Customer Agreement.pdf"), backend_root),
        chroma_dir=_resolve_path(os.getenv("CHROMA_DIR", "./data/chroma"), backend_root),
        chroma_collection=os.getenv("CHROMA_COLLECTION", "aws_customer_agreement"),
        rag_chroma_collection=os.getenv("RAG_CHROMA_COLLECTION", "aws_customer_agreement_rag_chunks"),
        sqlite_path=_resolve_path(os.getenv("SQLITE_PATH", "./data/usage.db"), backend_root),
        graph_sqlite_path=_resolve_path(os.getenv("GRAPH_SQLITE_PATH", "./data/graph.db"), backend_root),
        chunk_size=int(os.getenv("CHUNK_SIZE", "900")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "150")),
        default_top_k=int(os.getenv("DEFAULT_TOP_K", "3")),
        default_neighbors=int(os.getenv("DEFAULT_NEIGHBORS", "0")),
        embedding_base_url=os.getenv("OPENAI_EMBEDDING_BASE_URL", "http://localhost:11434/v1").strip().rstrip("/"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "qwen3-embedding:4b"),
        embedding_api_key=os.getenv("OPENAI_EMBEDDING_API_KEY") or None,
        chat_base_url=os.getenv("OPENAI_CHAT_BASE_URL", "http://localhost:11434/v1").strip().rstrip("/"),
        chat_model=os.getenv("OPENAI_CHAT_MODEL", "llama3.1"),
        chat_api_key=os.getenv("OPENAI_CHAT_API_KEY") or None,
        chat_max_tokens=int(os.getenv("OPENAI_CHAT_MAX_TOKENS", "700")),
        chat_temperature=float(os.getenv("OPENAI_CHAT_TEMPERATURE", "0.1")),
    )


def _resolve_path(value: str, root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()
