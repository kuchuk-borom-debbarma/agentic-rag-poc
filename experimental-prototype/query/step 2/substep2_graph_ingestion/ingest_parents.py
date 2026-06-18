import json
from pathlib import Path

from neo4j import GraphDatabase


URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password123")


def log(step, message):
    print(f"[Step 2.2] {step}: {message}")


def default_graph_path():
    return Path(__file__).resolve().parents[2] / "step 1" / "document_graph.json"


def load_graph(path):
    graph_path = Path(path)
    if not graph_path.exists():
        raise FileNotFoundError(f"Could not find {graph_path}")
    with open(graph_path, "r", encoding="utf-8") as handle:
        graph = json.load(handle)
    log("load", f"Loaded graph JSON from {graph_path}")
    return graph


def clear_database(tx):
    tx.run("MATCH (n) DETACH DELETE n")


def create_constraints(tx):
    statements = [
        """
        CREATE CONSTRAINT document_id_unique IF NOT EXISTS
        FOR (d:Document) REQUIRE d.document_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT section_id_unique IF NOT EXISTS
        FOR (s:Section) REQUIRE s.section_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
        FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT embedding_id_unique IF NOT EXISTS
        FOR (e:EmbeddingChunk) REQUIRE e.embedding_id IS UNIQUE
        """,
    ]
    for statement in statements:
        tx.run(statement)


def create_document(tx, document):
    tx.run(
        """
        MERGE (d:Document {document_id: $document_id})
        SET d.title = $title,
            d.source_path = $source_path,
            d.source_type = $source_type,
            d.source_hash = $source_hash,
            d.processor_version = $processor_version
        """,
        **document,
    )


def create_section(tx, document_id, section):
    tx.run(
        """
        MERGE (s:Section {section_id: $section_id})
        SET s.document_id = $document_id,
            s.section_number = $section_number,
            s.title = $title,
            s.level = $level,
            s.parent_section_id = $parent_section_id,
            s.child_section_ids = $child_section_ids,
            s.chunk_ids = $chunk_ids,
            s.order = $order
        """,
        document_id=document_id,
        **section,
    )


def create_chunk(tx, document_id, chunk):
    tx.run(
        """
        MERGE (c:Chunk {chunk_id: $chunk_id})
        SET c.document_id = $document_id,
            c.section_id = $section_id,
            c.section_number = $section_number,
            c.text = $text,
            c.chunk_type = $chunk_type,
            c.order = $order,
            c.page_start = $page_start,
            c.page_end = $page_end,
            c.previous_chunk_id = $previous_chunk_id,
            c.next_chunk_id = $next_chunk_id,
            c.referenced_section_ids = $referenced_section_ids,
            c.referenced_by_chunk_ids = $referenced_by_chunk_ids
        """,
        document_id=document_id,
        **chunk,
    )


def create_document_section_edges(tx, document_id, sections):
    for section in sections:
        if section.get("parent_section_id"):
            continue
        tx.run(
            """
            MATCH (d:Document {document_id: $document_id})
            MATCH (s:Section {section_id: $section_id})
            MERGE (d)-[:HAS_SECTION]->(s)
            """,
            document_id=document_id,
            section_id=section["section_id"],
        )


def create_section_hierarchy_edges(tx, sections):
    for section in sections:
        parent_id = section.get("parent_section_id")
        if not parent_id:
            continue
        tx.run(
            """
            MATCH (parent:Section {section_id: $parent_id})
            MATCH (child:Section {section_id: $child_id})
            MERGE (parent)-[:HAS_SECTION]->(child)
            """,
            parent_id=parent_id,
            child_id=section["section_id"],
        )


def create_section_chunk_edges(tx, sections):
    for section in sections:
        for chunk_id in section.get("chunk_ids", []):
            tx.run(
                """
                MATCH (s:Section {section_id: $section_id})
                MATCH (c:Chunk {chunk_id: $chunk_id})
                MERGE (s)-[:HAS_CHUNK]->(c)
                """,
                section_id=section["section_id"],
                chunk_id=chunk_id,
            )


def create_next_chunk_edges(tx, chunks):
    for chunk in chunks:
        next_chunk_id = chunk.get("next_chunk_id")
        if not next_chunk_id:
            continue
        tx.run(
            """
            MATCH (source:Chunk {chunk_id: $source_id})
            MATCH (target:Chunk {chunk_id: $target_id})
            MERGE (source)-[:NEXT_CHUNK]->(target)
            """,
            source_id=chunk["chunk_id"],
            target_id=next_chunk_id,
        )


def create_reference_edges(tx, chunks):
    for chunk in chunks:
        for section_id in chunk.get("referenced_section_ids", []):
            tx.run(
                """
                MATCH (source:Chunk {chunk_id: $chunk_id})
                MATCH (target:Section {section_id: $section_id})
                MERGE (source)-[:REFERENCES]->(target)
                """,
                chunk_id=chunk["chunk_id"],
                section_id=section_id,
            )


def fetch_counts(tx):
    labels = ["Document", "Section", "Chunk", "EmbeddingChunk"]
    rels = ["HAS_SECTION", "HAS_CHUNK", "NEXT_CHUNK", "REFERENCES", "HAS_EMBEDDING"]
    counts = {}
    for label in labels:
        counts[label] = tx.run(f"MATCH (n:{label}) RETURN count(n) AS count").single()["count"]
    for rel in rels:
        counts[rel] = tx.run(
            "MATCH ()-[r]->() WHERE type(r) = $rel RETURN count(r) AS count",
            rel=rel,
        ).single()["count"]
    return counts


def ingest_graph(session, graph):
    document = graph["document"]
    sections = graph["sections"]
    chunks = graph["chunks"]
    document_id = document["document_id"]

    log("schema", "Creating Neo4j constraints")
    session.execute_write(create_constraints)

    log("reset", "Clearing existing graph data")
    session.execute_write(clear_database)

    log("nodes", "Creating Document node")
    session.execute_write(create_document, document)

    log("nodes", f"Creating {len(sections)} Section nodes")
    for section in sections:
        session.execute_write(create_section, document_id, section)

    log("nodes", f"Creating {len(chunks)} Chunk nodes")
    for chunk in chunks:
        session.execute_write(create_chunk, document_id, chunk)

    log("edges", "Creating Document/Section hierarchy")
    session.execute_write(create_document_section_edges, document_id, sections)
    session.execute_write(create_section_hierarchy_edges, sections)

    log("edges", "Creating Section/Chunk and NEXT_CHUNK relationships")
    session.execute_write(create_section_chunk_edges, sections)
    session.execute_write(create_next_chunk_edges, chunks)

    log("edges", "Creating Chunk -> Section REFERENCES relationships")
    session.execute_write(create_reference_edges, chunks)


def main():
    graph_path = default_graph_path()
    graph = load_graph(graph_path)

    log("connect", f"Connecting to Neo4j at {URI}")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            ingest_graph(session, graph)
            counts = session.execute_read(fetch_counts)
    finally:
        driver.close()

    log(
        "done",
        " | ".join(f"{key}={value}" for key, value in counts.items()),
    )


if __name__ == "__main__":
    main()
