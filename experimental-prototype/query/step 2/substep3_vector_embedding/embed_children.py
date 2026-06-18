import os
import argparse
import shutil
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

warnings.filterwarnings("ignore", message=".*langchain-experimental.*", category=DeprecationWarning)
from langchain_experimental.text_splitter import SemanticChunker
from neo4j import GraphDatabase


URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password123")
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen3-embedding:4b"
REQUEST_TIMEOUT_SECONDS = 30
PROGRESS_BAR_WIDTH = 18


def log(step, message):
    print(f"[Step 2.3] {step}: {message}")


def normalize_base_url(value):
    base_url = (value or DEFAULT_BASE_URL).strip().rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return base_url


class OpenAIEmbeddings(Embeddings):
    def __init__(self, base_url, model, api_key=None, timeout=REQUEST_TIMEOUT_SECONDS):
        self.base_url = normalize_base_url(base_url)
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def _post_embeddings(self, text):
        try:
            response = self.session.post(
                f"{self.base_url}/embeddings",
                json={"input": text, "model": self.model},
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if "data" not in payload or not payload["data"]:
                raise RuntimeError(f"Embedding API response missing data: {payload}")
            return payload["data"][0]["embedding"]
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Could not connect to embedding server at {self.base_url}. Is the server running?")
        except Exception as e:
            raise RuntimeError(f"Embedding failed: {e}")

    def embed_query(self, text):
        return self._post_embeddings(text)

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def health_check(self):
        # Some providers might not have /models, but let's try a simple probe
        try:
            response = self.session.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=8,
            )
            response.raise_for_status()
            return response.json()
        except:
            # If /models fails, we'll rely on the test_vector in main
            return {"status": "unknown"}


@dataclass
class EmbeddingTask:
    embedding_id: str
    chunk_id: str
    section_id: str
    section_number: str
    text: str
    order: int


class ProgressPrinter:
    def __init__(self, total):
        self.total = max(total, 1)
        self.is_tty = sys.stdout.isatty()
        self.last_line_length = 0
        self.last_non_tty_print = 0
        self.started_at = time.time()

    def render(self, completed, label):
        left = max(self.total - completed, 0)
        ratio = completed / self.total
        filled = int(ratio * PROGRESS_BAR_WIDTH)
        bar = "#" * filled + "-" * (PROGRESS_BAR_WIDTH - filled)
        return (
            f"[7/8] Vectorizing | {completed}/{self.total} done | "
            f"{left} left | {bar} | {label}"
        )

    def update(self, completed, label):
        line = self.render(completed, label)
        if self.is_tty:
            width = shutil.get_terminal_size((120, 20)).columns
            trimmed = line[: max(width - 1, 20)]
            padded = trimmed.ljust(self.last_line_length)
            print(f"\r{padded}", end="", flush=True)
            self.last_line_length = len(trimmed)
            return

        if completed == self.total or completed - self.last_non_tty_print >= 25:
            print(line, flush=True)
            self.last_non_tty_print = completed

    def finish(self):
        elapsed = time.time() - self.started_at
        if self.is_tty:
            print()
        log("progress", f"Embedded {self.total} vectors in {elapsed:.1f}s")


def load_environment():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    base_url = normalize_base_url(os.environ.get("OPENAI_EMBEDDING_BASE_URL"))
    model = os.environ.get("OPENAI_EMBEDDING_MODEL", DEFAULT_MODEL)
    api_key = os.environ.get("OPENAI_EMBEDDING_API_KEY")
    log("config", f"Base URL: {base_url}")
    log("config", f"Model: {model}")
    return base_url, model, api_key


def explain_connection_error(base_url, error):
    message = str(error)
    guidance = [
        f"Embedding server is unreachable at {base_url}.",
        "Verify Ollama or LM Studio is running.",
        "Verify OPENAI_EMBEDDING_BASE_URL points to the active host.",
        f"Original error: {message}",
    ]
    return "\n".join(guidance)


def connect_driver():
    log("connect", f"Connecting to Neo4j at {URI}")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    driver.verify_connectivity()
    return driver


def fetch_chunks(tx):
    result = tx.run(
        """
        MATCH (c:Chunk)
        RETURN c.chunk_id AS chunk_id,
               c.section_id AS section_id,
               c.section_number AS section_number,
               c.text AS text,
               c.order AS order
        ORDER BY c.order
        """
    )
    return [dict(record) for record in result]


def clear_embeddings(tx):
    tx.run("MATCH (e:EmbeddingChunk) DETACH DELETE e")


def recreate_vector_index(tx, dimension):
    tx.run("DROP INDEX semantic_embeddings IF EXISTS")
    tx.run(
        f"""
        CREATE VECTOR INDEX semantic_embeddings IF NOT EXISTS
        FOR (e:EmbeddingChunk) ON (e.embedding)
        OPTIONS {{indexConfig: {{
          `vector.dimensions`: {dimension},
          `vector.similarity_function`: 'cosine'
        }}}}
        """
    )


def insert_embedding(tx, task, embedding, model, dimension):
    tx.run(
        """
        MATCH (c:Chunk {chunk_id: $chunk_id})
        MERGE (e:EmbeddingChunk {embedding_id: $embedding_id})
        SET e.chunk_id = $chunk_id,
            e.section_id = $section_id,
            e.section_number = $section_number,
            e.text = $text,
            e.order = $order,
            e.embedding_model = $model,
            e.embedding_dimension = $dimension,
            e.embedding = $embedding
        MERGE (c)-[:HAS_EMBEDDING]->(e)
        """,
        embedding_id=task.embedding_id,
        chunk_id=task.chunk_id,
        section_id=task.section_id,
        section_number=task.section_number,
        text=task.text,
        order=task.order,
        model=model,
        dimension=dimension,
        embedding=embedding,
    )


def split_chunk_text(splitter, chunk):
    text = (chunk["text"] or "").strip()
    if not text:
        return []
    try:
        docs = splitter.split_documents([Document(page_content=text)])
    except Exception as error:
        log("split", f"{chunk['chunk_id']} semantic split failed; using original chunk. Error: {error}")
        return [text]
    texts = [doc.page_content.strip() for doc in docs if doc.page_content and doc.page_content.strip()]
    return texts or [text]


def build_embedding_tasks(chunks, splitter):
    log("split", f"Precomputing semantic splits for {len(chunks)} chunks")
    tasks = []
    for chunk in chunks:
        texts = split_chunk_text(splitter, chunk)
        for index, text in enumerate(texts):
            tasks.append(
                EmbeddingTask(
                    embedding_id=f"emb_{chunk['chunk_id']}_{index:02d}",
                    chunk_id=chunk["chunk_id"],
                    section_id=chunk["section_id"],
                    section_number=chunk["section_number"],
                    text=text,
                    order=index,
                )
            )
    log("split", f"Prepared {len(tasks)} embedding tasks")
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Create EmbeddingChunk nodes from Chunk nodes.")
    parser.add_argument("--health-only", action="store_true", help="Check backend and exit")
    args = parser.parse_args()

    base_url, model, api_key = load_environment()
    embeddings = OpenAIEmbeddings(base_url=base_url, model=model, api_key=api_key)

    log("health", "Checking embedding server health")
    try:
        embeddings.health_check()
        test_vector = embeddings.embed_query("hello")
    except Exception as error:
        raise SystemExit(explain_connection_error(base_url, error))

    dimension = len(test_vector)
    log("health", f"Embedding backend ready; dimension={dimension}")
    if args.health_only:
        log("done", "Health check complete")
        return

    driver = connect_driver()
    try:
        with driver.session() as session:
            chunks = session.execute_read(fetch_chunks)
            if not chunks:
                raise RuntimeError("No Chunk nodes found. Run Step 2.2 ingestion first.")
            log("load", f"Fetched {len(chunks)} Chunk nodes")

            splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
            tasks = build_embedding_tasks(chunks, splitter)
            if not tasks:
                raise RuntimeError("No embedding tasks produced from Chunk nodes.")

            log("schema", "Recreating vector index")
            session.execute_write(recreate_vector_index, dimension)

            log("reset", "Clearing old EmbeddingChunk nodes")
            session.execute_write(clear_embeddings)

            progress = ProgressPrinter(len(tasks))
            for completed, task in enumerate(tasks, start=1):
                vector = embeddings.embed_query(task.text)
                if len(vector) != dimension:
                    raise RuntimeError(
                        f"Embedding dimension changed for {task.embedding_id}: "
                        f"expected {dimension}, got {len(vector)}"
                    )
                session.execute_write(insert_embedding, task, vector, model, dimension)
                progress.update(completed, f"{task.chunk_id} -> {task.embedding_id}")
            progress.finish()
    finally:
        driver.close()

    log("done", "EmbeddingChunk graph complete")


if __name__ == "__main__":
    main()
