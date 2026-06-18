"""Internal hierarchical document layout models."""

from dataclasses import dataclass, field
from typing import Literal, TypeAlias


@dataclass
class Reference:
    """Inline reference from one content block to another section."""

    referenced_section_id: str
    start_index: int
    end_index: int


@dataclass
class ContentBlock:
    """Text content owned by a section."""

    data: str
    references: list[Reference] = field(default_factory=list)
    type: Literal["content"] = "content"


@dataclass
class SectionRefBlock:
    """Layout marker pointing to a child section."""

    section_id: str
    type: Literal["section-ref"] = "section-ref"


LayoutBlock: TypeAlias = ContentBlock | SectionRefBlock


@dataclass
class Section:
    """Hierarchical section with mixed content and subsection layout."""

    id: str
    title: str
    layout: list[LayoutBlock]
    parent: str | None


@dataclass
class ChunkedContent:
    """Semantically chunked content with lineage and cached embedding."""

    section_id: str
    layout_index: int
    chunk_index: int
    text: str
    references: list[Reference]
    embedding: list[float] = field(default_factory=list)


@dataclass
class GraphChunk:
    """Graph identity and lineage for a semantic chunk."""

    id: str
    section_id: str
    layout_index: int
    chunk_index: int


@dataclass
class GraphMaps:
    """Query-navigation graph maps built from sections and chunked content."""

    section_hierarchy: dict[str, list[str]]
    chunk_sequence: dict[str, str | None]
    chunk_to_section: dict[str, str]
    chunk_references: dict[str, list[str]]
    sections: dict[str, Section]
    chunks: dict[str, ChunkedContent]


@dataclass
class VectorMatch:
    """Semantic vector match with graph lookup metadata."""

    chunk_id: str
    text: str
    score: float
    section_id: str
    parent_section_id: str | None
    layout_index: int
    chunk_index: int
    referenced_section_ids: list[str]
