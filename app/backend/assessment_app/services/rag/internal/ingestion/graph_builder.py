"""Build lightweight graph maps from parsed sections and semantic chunks."""

from assessment_app.services.rag.internal.ingestion.models import ChunkedContent, GraphMaps, Section
from assessment_app.services.rag.internal.ingestion.graph_validator import GraphValidationError, GraphValidator


class GraphBuilder:
    """Create query-navigation maps without graph database complexity."""

    def __init__(self, validator: GraphValidator | None = None) -> None:
        self._validator = validator or GraphValidator()

    def build(self, sections: list[Section], chunks: list[ChunkedContent]) -> GraphMaps:
        """Return validated graph maps for Stage 4 retrieval expansion."""
        self._validate_unique_ids(sections, chunks)
        graph = GraphMaps(
            section_hierarchy=self._section_hierarchy(sections),
            chunk_sequence=self._chunk_sequence(chunks),
            chunk_to_section={self._chunk_id(chunk): chunk.section_id for chunk in chunks},
            chunk_references={self._chunk_id(chunk): self._referenced_sections(chunk) for chunk in chunks},
            sections={section.id: section for section in sections},
            chunks={self._chunk_id(chunk): chunk for chunk in chunks},
        )
        self._validator.validate(graph)
        return graph

    def _validate_unique_ids(self, sections: list[Section], chunks: list[ChunkedContent]) -> None:
        errors: list[str] = []
        section_ids = [section.id for section in sections]
        for section_id in section_ids:
            if section_ids.count(section_id) > 1 and f"duplicate section id: {section_id}" not in errors:
                errors.append(f"duplicate section id: {section_id}")

        chunk_ids = [self._chunk_id(chunk) for chunk in chunks]
        for chunk_id in chunk_ids:
            if chunk_ids.count(chunk_id) > 1 and f"duplicate chunk id: {chunk_id}" not in errors:
                errors.append(f"duplicate chunk id: {chunk_id}")

        if errors:
            raise GraphValidationError(errors)

    def _section_hierarchy(self, sections: list[Section]) -> dict[str, list[str]]:
        hierarchy = {section.id: [] for section in sections}
        for section in sections:
            if section.parent:
                hierarchy.setdefault(section.parent, []).append(section.id)
        return hierarchy

    def _chunk_sequence(self, chunks: list[ChunkedContent]) -> dict[str, str | None]:
        sequence = {self._chunk_id(chunk): None for chunk in chunks}
        groups: dict[tuple[str, int], list[ChunkedContent]] = {}
        for chunk in chunks:
            groups.setdefault((chunk.section_id, chunk.layout_index), []).append(chunk)

        for group_chunks in groups.values():
            ordered = sorted(group_chunks, key=lambda chunk: chunk.chunk_index)
            for index, chunk in enumerate(ordered[:-1]):
                sequence[self._chunk_id(chunk)] = self._chunk_id(ordered[index + 1])
        return sequence

    def _referenced_sections(self, chunk: ChunkedContent) -> list[str]:
        referenced: list[str] = []
        for reference in chunk.references:
            if reference.referenced_section_id not in referenced:
                referenced.append(reference.referenced_section_id)
        return referenced

    def _chunk_id(self, chunk: ChunkedContent) -> str:
        return f"{chunk.section_id}:{chunk.layout_index}:{chunk.chunk_index}"
