import json
from pathlib import Path

from neo4j import GraphDatabase


URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password123")


def log(message):
    print(f"[Check] {message}")


def graph_json_path():
    return Path(__file__).resolve().parent / "step 1" / "document_graph.json"


def expected_reference_count():
    path = graph_json_path()
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        graph = json.load(handle)
    return sum(len(chunk.get("referenced_section_ids", [])) for chunk in graph.get("chunks", []))


def scalar(session, query, **params):
    return session.run(query, **params).single()["value"]


def main():
    log(f"Connecting to Neo4j at {URI}")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            documents = scalar(session, "MATCH (n:Document) RETURN count(n) AS value")
            sections = scalar(session, "MATCH (n:Section) RETURN count(n) AS value")
            chunks = scalar(session, "MATCH (n:Chunk) RETURN count(n) AS value")
            embeddings = scalar(session, "MATCH (n:EmbeddingChunk) RETURN count(n) AS value")

            has_section = scalar(session, "MATCH ()-[r]->() WHERE type(r) = 'HAS_SECTION' RETURN count(r) AS value")
            has_chunk = scalar(session, "MATCH ()-[r]->() WHERE type(r) = 'HAS_CHUNK' RETURN count(r) AS value")
            next_chunk = scalar(session, "MATCH ()-[r]->() WHERE type(r) = 'NEXT_CHUNK' RETURN count(r) AS value")
            references = scalar(session, "MATCH ()-[r]->() WHERE type(r) = 'REFERENCES' RETURN count(r) AS value")
            has_embedding = scalar(session, "MATCH ()-[r]->() WHERE type(r) = 'HAS_EMBEDDING' RETURN count(r) AS value")

            chunk_without_section = scalar(
                session,
                """
                MATCH (c:Chunk)
                WHERE NOT (:Section)-[:HAS_CHUNK]->(c)
                RETURN count(c) AS value
                """,
            )
            chunk_without_embedding = scalar(
                session,
                """
                MATCH (c:Chunk)
                WHERE NOT EXISTS {
                  MATCH (c)-[r]->(:EmbeddingChunk)
                  WHERE type(r) = 'HAS_EMBEDDING'
                }
                RETURN count(c) AS value
                """,
            )
            sample_embedding_dim = scalar(
                session,
                """
                OPTIONAL MATCH (e:EmbeddingChunk)
                WITH e
                ORDER BY e.embedding_id
                RETURN coalesce(size(e.embedding), 0) AS value
                LIMIT 1
                """,
            )
    finally:
        driver.close()

    expected_refs = expected_reference_count()
    expected_next = max(chunks - 1, 0)

    log(f"Document nodes: {documents}")
    log(f"Section nodes: {sections}")
    log(f"Chunk nodes: {chunks}")
    log(f"EmbeddingChunk nodes: {embeddings}")
    log(f"HAS_SECTION relationships: {has_section}")
    log(f"HAS_CHUNK relationships: {has_chunk}")
    log(f"NEXT_CHUNK relationships: {next_chunk}")
    log(f"REFERENCES relationships: {references}")
    log(f"HAS_EMBEDDING relationships: {has_embedding}")
    log(f"Sample embedding dimension: {sample_embedding_dim}")

    errors = []
    if documents != 1:
        errors.append(f"expected 1 Document, got {documents}")
    if chunks and next_chunk != expected_next:
        errors.append(f"expected NEXT_CHUNK={expected_next}, got {next_chunk}")
    if has_chunk != chunks:
        errors.append(f"expected HAS_CHUNK={chunks}, got {has_chunk}")
    if expected_refs is not None and references != expected_refs:
        errors.append(f"expected REFERENCES={expected_refs}, got {references}")
    if chunk_without_section:
        errors.append(f"{chunk_without_section} chunks missing Section parent")
    if chunk_without_embedding:
        errors.append(f"{chunk_without_embedding} chunks missing embeddings")
    if embeddings == 0 or has_embedding == 0 or sample_embedding_dim == 0:
        errors.append("embedding graph missing vectors")

    if errors:
        joined = "\n- ".join(errors)
        raise SystemExit(f"Graph verification failed:\n- {joined}")

    log("Graph verification OK")


if __name__ == "__main__":
    main()
