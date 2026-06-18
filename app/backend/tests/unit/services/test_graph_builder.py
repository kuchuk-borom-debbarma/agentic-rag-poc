"""Unit tests for Stage 3 graph-map building."""

import pytest

from assessment_app.services.rag.internal.ingestion.graph_builder import GraphBuilder
from assessment_app.services.rag.internal.ingestion.graph_validator import GraphValidationError, GraphValidator
from assessment_app.services.rag.internal.ingestion.models import ChunkedContent, GraphMaps, Reference, Section


def test_graph_builder_creates_hierarchy_sequence_ownership_and_references():
    sections = [
        Section(id="section_1", title="Foo", parent=None, layout=[]),
        Section(id="section_2", title="Bar", parent="section_1", layout=[]),
    ]
    chunks = [
        ChunkedContent(
            section_id="section_1",
            layout_index=2,
            chunk_index=0,
            text="See Bar.",
            references=[Reference("section_2", 4, 7), Reference("section_2", 4, 7)],
            embedding=[0.1],
        ),
        ChunkedContent(
            section_id="section_1",
            layout_index=2,
            chunk_index=1,
            text="More Foo.",
            references=[],
            embedding=[0.2],
        ),
        ChunkedContent(
            section_id="section_2",
            layout_index=0,
            chunk_index=0,
            text="Bar content.",
            references=[],
            embedding=[0.3],
        ),
    ]

    graph = GraphBuilder().build(sections, chunks)

    assert graph.section_hierarchy == {"section_1": ["section_2"], "section_2": []}
    assert graph.chunk_sequence == {
        "section_1:2:0": "section_1:2:1",
        "section_1:2:1": None,
        "section_2:0:0": None,
    }
    assert graph.chunk_to_section == {
        "section_1:2:0": "section_1",
        "section_1:2:1": "section_1",
        "section_2:0:0": "section_2",
    }
    assert graph.chunk_references == {
        "section_1:2:0": ["section_2"],
        "section_1:2:1": [],
        "section_2:0:0": [],
    }


def test_graph_sequence_links_only_same_section_and_layout():
    sections = [Section(id="section_1", title="Foo", parent=None, layout=[])]
    chunks = [
        ChunkedContent("section_1", 0, 0, "A", []),
        ChunkedContent("section_1", 1, 0, "B", []),
    ]

    graph = GraphBuilder().build(sections, chunks)

    assert graph.chunk_sequence == {"section_1:0:0": None, "section_1:1:0": None}


def test_graph_builder_rejects_duplicate_chunk_ids():
    sections = [Section(id="section_1", title="Foo", parent=None, layout=[])]
    chunks = [
        ChunkedContent("section_1", 0, 0, "A", []),
        ChunkedContent("section_1", 0, 0, "B", []),
    ]

    with pytest.raises(GraphValidationError):
        GraphBuilder().build(sections, chunks)


def test_graph_validator_rejects_missing_child_section():
    graph = _valid_graph()
    graph.section_hierarchy["section_1"].append("section_missing")

    with pytest.raises(GraphValidationError):
        GraphValidator().validate(graph)


def test_graph_validator_rejects_missing_sequence_target():
    graph = _valid_graph()
    graph.chunk_sequence["section_1:0:0"] = "chunk_missing"

    with pytest.raises(GraphValidationError):
        GraphValidator().validate(graph)


def test_graph_validator_rejects_missing_reference_target():
    graph = _valid_graph()
    graph.chunk_references["section_1:0:0"] = ["section_missing"]

    with pytest.raises(GraphValidationError):
        GraphValidator().validate(graph)


def _valid_graph() -> GraphMaps:
    section = Section(id="section_1", title="Foo", parent=None, layout=[])
    chunk = ChunkedContent("section_1", 0, 0, "Foo", [])
    return GraphMaps(
        section_hierarchy={"section_1": []},
        chunk_sequence={"section_1:0:0": None},
        chunk_to_section={"section_1:0:0": "section_1"},
        chunk_references={"section_1:0:0": []},
        sections={"section_1": section},
        chunks={"section_1:0:0": chunk},
    )
