"""Validation for Stage 3 graph maps."""

from assessment_app.services.rag.internal.ingestion.models import GraphMaps


class GraphValidationError(ValueError):
    """Raised when graph maps contain broken links."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Graph validation failed: " + "; ".join(errors))


class GraphValidator:
    """Validate lightweight graph-map invariants."""

    def validate(self, graph: GraphMaps) -> None:
        errors: list[str] = []
        section_ids = set(graph.sections)
        chunk_ids = set(graph.chunks)

        for parent_id, child_ids in graph.section_hierarchy.items():
            if parent_id not in section_ids:
                errors.append(f"section hierarchy parent missing: {parent_id}")
            for child_id in child_ids:
                if child_id not in section_ids:
                    errors.append(f"section hierarchy child missing: {child_id}")

        for chunk_id, next_chunk_id in graph.chunk_sequence.items():
            if chunk_id not in chunk_ids:
                errors.append(f"chunk sequence source missing: {chunk_id}")
            if next_chunk_id and next_chunk_id not in chunk_ids:
                errors.append(f"chunk sequence target missing: {next_chunk_id}")

        for chunk_id in chunk_ids:
            if chunk_id not in graph.chunk_to_section:
                errors.append(f"chunk missing chunk_to_section entry: {chunk_id}")

        for chunk_id, section_id in graph.chunk_to_section.items():
            if chunk_id not in chunk_ids:
                errors.append(f"chunk_to_section source missing: {chunk_id}")
            if section_id not in section_ids:
                errors.append(f"chunk_to_section section missing: {section_id}")

        for chunk_id, referenced_section_ids in graph.chunk_references.items():
            if chunk_id not in chunk_ids:
                errors.append(f"chunk reference source missing: {chunk_id}")
            for section_id in referenced_section_ids:
                if section_id not in section_ids:
                    errors.append(f"chunk reference target missing: {section_id}")

        if errors:
            raise GraphValidationError(errors)
