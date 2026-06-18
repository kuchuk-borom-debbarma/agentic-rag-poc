from dataclasses import dataclass

from neo4j import GraphDatabase


@dataclass(frozen=True)
class ContextBlock:
    source_id: str
    chunk_id: str
    embedding_id: str | None
    section_id: str
    section_number: str
    section_title: str
    page_start: int | None
    page_end: int | None
    score: float | None
    order: int
    text: str

    @property
    def label(self):
        if self.section_number == "front_matter":
            section = "Front Matter"
        else:
            section = f"Section {self.section_number}"

        if self.section_title:
            section += f" - {self.section_title}"
        page = self.page_start if self.page_start == self.page_end else f"{self.page_start}-{self.page_end}"
        return f"{section} | chunk={self.chunk_id} | page {page}"


class GraphTools:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def verify(self):
        self.driver.verify_connectivity()

    def semantic_search(self, embedding, top_k):
        query = """
        CALL db.index.vector.queryNodes('semantic_embeddings', $top_k, $embedding)
        YIELD node, score
        MATCH (c:Chunk {chunk_id: node.chunk_id})
        OPTIONAL MATCH (s:Section {section_id: c.section_id})
        RETURN node.embedding_id AS embedding_id,
               c.chunk_id AS chunk_id,
               c.section_id AS section_id,
               c.section_number AS section_number,
               coalesce(s.title, '') AS section_title,
               c.page_start AS page_start,
               c.page_end AS page_end,
               c.order AS order,
               c.text AS text,
               score AS score
        ORDER BY score DESC
        """
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query, top_k=top_k, embedding=embedding)]

    def get_neighbors(self, orders, before=1, after=1):
        if not orders or (before == 0 and after == 0):
            return []
        windows = [{"start": order - before, "end": order + after} for order in orders]
        query = """
        UNWIND $windows AS window
        MATCH (c:Chunk)
        WHERE c.order >= window.start AND c.order <= window.end
        OPTIONAL MATCH (s:Section {section_id: c.section_id})
        RETURN null AS embedding_id,
               c.chunk_id AS chunk_id,
               c.section_id AS section_id,
               c.section_number AS section_number,
               coalesce(s.title, '') AS section_title,
               c.page_start AS page_start,
               c.page_end AS page_end,
               c.order AS order,
               c.text AS text,
               null AS score
        ORDER BY c.order
        """
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query, windows=windows)]

    def get_section_chunks(self, section_numbers):
        if not section_numbers:
            return []
        query = """
        MATCH (s:Section)
        WHERE s.section_number IN $section_numbers
        MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
        RETURN null AS embedding_id,
               c.chunk_id AS chunk_id,
               c.section_id AS section_id,
               c.section_number AS section_number,
               coalesce(s.title, '') AS section_title,
               c.page_start AS page_start,
               c.page_end AS page_end,
               c.order AS order,
               c.text AS text,
               null AS score
        ORDER BY c.order
        """
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query, section_numbers=section_numbers)]

    def get_referenced_sections(self, chunk_ids):
        if not chunk_ids:
            return []
        query = """
        MATCH (source:Chunk)-[:REFERENCES]->(s:Section)
        WHERE source.chunk_id IN $chunk_ids
        OPTIONAL MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
        WITH s, c
        ORDER BY c.order
        WITH s, collect(c)[0..2] AS chunks
        UNWIND chunks AS c
        RETURN null AS embedding_id,
               c.chunk_id AS chunk_id,
               c.section_id AS section_id,
               c.section_number AS section_number,
               coalesce(s.title, '') AS section_title,
               c.page_start AS page_start,
               c.page_end AS page_end,
               c.order AS order,
               c.text AS text,
               null AS score
        ORDER BY c.order
        """
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query, chunk_ids=chunk_ids)]


def rows_to_context_blocks(rows):
    deduped = {}
    for row in rows:
        chunk_id = row["chunk_id"]
        existing = deduped.get(chunk_id)
        if existing and existing.get("score") is not None:
            continue
        deduped[chunk_id] = row

    blocks = []
    for index, row in enumerate(sorted(deduped.values(), key=lambda item: item["order"]), start=1):
        blocks.append(
            ContextBlock(
                source_id=f"S{index}",
                chunk_id=row["chunk_id"],
                embedding_id=row.get("embedding_id"),
                section_id=row["section_id"],
                section_number=row["section_number"],
                section_title=row["section_title"],
                page_start=row.get("page_start"),
                page_end=row.get("page_end"),
                score=row.get("score"),
                order=row["order"],
                text=row["text"],
            )
        )
    return blocks
