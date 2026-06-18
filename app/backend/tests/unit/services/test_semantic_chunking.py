"""Unit tests for semantic chunking."""

from assessment_app.services.rag.internal.ingestion.models import (
    ContentBlock,
    Reference,
    Section,
    SectionRefBlock,
)
from assessment_app.services.rag.internal.ingestion.semantic_chunker import SemanticChunker
from assessment_app.services.rag.internal.ingestion.service_impl import DefaultSemanticChunkingService


def test_tiny_content_block_returns_one_chunk_with_reference_indexes():
    sections = [
        Section(
            id="section_1",
            title="Foo",
            parent=None,
            layout=[
                ContentBlock(
                    data="More foo content. See Bar for details.",
                    references=[Reference("section_2", 22, 25)],
                )
            ],
        )
    ]

    chunks = SemanticChunker(max_chars=300).chunk(sections)

    assert len(chunks) == 1
    assert chunks[0].text == "More foo content. See Bar for details."
    assert chunks[0].references == [Reference("section_2", 22, 25)]


def test_large_content_splits_by_sentence_and_reindexes_later_reference():
    text = "More foo content. See Bar for details. Also check Bar documentation."
    sections = [
        Section(
            id="section_1",
            title="Foo",
            parent=None,
            layout=[
                ContentBlock(
                    data=text,
                    references=[
                        Reference("section_2", 22, 25),
                        Reference("section_2", 50, 53),
                    ],
                )
            ],
        )
    ]

    chunks = SemanticChunker(max_chars=45).chunk(sections)

    assert [chunk.text for chunk in chunks] == [
        "More foo content. See Bar for details.",
        "Also check Bar documentation.",
    ]
    assert chunks[0].references == [Reference("section_2", 22, 25)]
    assert chunks[1].references == [Reference("section_2", 11, 14)]


def test_chunk_lineage_uses_section_layout_and_resets_chunk_index_per_block():
    sections = [
        Section(
            id="section_1",
            title="Foo",
            parent=None,
            layout=[
                ContentBlock("One. Two."),
                SectionRefBlock("section_2"),
                ContentBlock("Three. Four."),
            ],
        )
    ]

    chunks = SemanticChunker(max_chars=6).chunk(sections)

    assert [(chunk.section_id, chunk.layout_index, chunk.chunk_index) for chunk in chunks] == [
        ("section_1", 0, 0),
        ("section_1", 0, 1),
        ("section_1", 2, 0),
        ("section_1", 2, 1),
    ]


def test_section_ref_blocks_do_not_create_chunks():
    sections = [Section(id="section_1", title="Foo", parent=None, layout=[SectionRefBlock("section_2")])]

    assert SemanticChunker().chunk(sections) == []


def test_semantic_chunking_service_embeds_once_and_attaches_vectors():
    sections = [
        Section(
            id="section_1",
            title="Foo",
            parent=None,
            layout=[ContentBlock("One. Two.")],
        )
    ]
    embedding_client = _RecordingEmbeddingClient()

    chunks = DefaultSemanticChunkingService(
        chunker=SemanticChunker(max_chars=6),
        embedding_client=embedding_client,
    ).chunk(sections)

    assert embedding_client.calls == [["One.", "Two."]]
    assert [chunk.embedding for chunk in chunks] == [[1.0], [2.0]]


class _RecordingEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(index)] for index, _ in enumerate(texts, start=1)]
