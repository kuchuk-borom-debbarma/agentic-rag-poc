"""Structure validation for parsed RAG ingestion sections."""

from collections import Counter

from assessment_app.services.rag.internal.ingestion.models import ContentBlock, Section, SectionRefBlock


class StructureValidationError(ValueError):
    """Raised when parsed section structure has broken links."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Structure validation failed: " + "; ".join(errors))


class StructureValidator:
    """Validate section hierarchy and resolved references."""

    def validate(self, sections: list[Section]) -> None:
        errors: list[str] = []
        section_ids = [section.id for section in sections]
        section_id_set = set(section_ids)

        for section_id, count in Counter(section_ids).items():
            if count > 1:
                errors.append(f"duplicate section id: {section_id}")

        for section in sections:
            if section.parent and section.parent not in section_id_set:
                errors.append(f"{section.id} parent missing: {section.parent}")

            for block in section.layout:
                if isinstance(block, SectionRefBlock):
                    self._validate_section_ref(block, section, sections, section_id_set, errors)
                elif isinstance(block, ContentBlock):
                    for reference in block.references:
                        if reference.referenced_section_id not in section_id_set:
                            errors.append(
                                f"{section.id} reference target missing: {reference.referenced_section_id}"
                            )

        if errors:
            raise StructureValidationError(errors)

    def _validate_section_ref(
        self,
        block: SectionRefBlock,
        section: Section,
        sections: list[Section],
        section_id_set: set[str],
        errors: list[str],
    ) -> None:
        if block.section_id not in section_id_set:
            errors.append(f"{section.id} child section missing: {block.section_id}")
            return

        child = next(candidate for candidate in sections if candidate.id == block.section_id)
        if child.parent != section.id:
            errors.append(f"{section.id} child parent mismatch: {block.section_id}")
