import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


QUERY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = QUERY_ROOT.parent
EMBED_ENV_PATH = QUERY_ROOT / "step 2" / "substep3_vector_embedding" / ".env"


def _normalize_base_url(value, default):
    base_url = (value or default).strip().rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return base_url


@dataclass(frozen=True)
class QueryConfig:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    embedding_base_url: str
    embedding_model: str
    embedding_api_key: str | None
    chat_base_url: str
    chat_model: str
    chat_api_key: str | None
    chat_max_tokens: int | None
    chat_top_p: float | None
    chat_enable_thinking: bool
    request_timeout_seconds: int

    @property
    def neo4j_auth(self):
        return (self.neo4j_user, self.neo4j_password)


def load_config():
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(EMBED_ENV_PATH)
    load_dotenv(QUERY_ROOT / "agents" / ".env")

    embedding_base = _normalize_base_url(
        os.environ.get("OPENAI_EMBEDDING_BASE_URL"),
        "http://localhost:11434/v1",
    )
    chat_base = _normalize_base_url(
        os.environ.get("OPENAI_CHAT_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or embedding_base,
        embedding_base,
    )

    return QueryConfig(
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "password123"),
        embedding_base_url=embedding_base,
        embedding_model=os.environ.get("OPENAI_EMBEDDING_MODEL", "qwen3-embedding:4b"),
        embedding_api_key=os.environ.get("OPENAI_EMBEDDING_API_KEY"),
        chat_base_url=chat_base,
        chat_model=os.environ.get("OPENAI_CHAT_MODEL", os.environ.get("OPENAI_MODEL", "google/gemma-4-31b-it")),
        chat_api_key=os.environ.get("OPENAI_CHAT_API_KEY") or os.environ.get("NVIDIA_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        chat_max_tokens=_optional_int(os.environ.get("OPENAI_CHAT_MAX_TOKENS")),
        chat_top_p=_optional_float(os.environ.get("OPENAI_CHAT_TOP_P")),
        chat_enable_thinking=_env_bool(os.environ.get("OPENAI_CHAT_ENABLE_THINKING"), default=False),
        request_timeout_seconds=int(os.environ.get("QUERY_REQUEST_TIMEOUT_SECONDS", "60")),
    )


def _optional_int(value):
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value):
    if value is None or value == "":
        return None
    return float(value)


def _env_bool(value, default=False):
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
