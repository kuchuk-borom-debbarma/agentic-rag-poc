"""Shared HTTP response DTOs used by multiple route modules."""

from pydantic import BaseModel


class SourceResponse(BaseModel):
    """HTTP response shape for a single retrieved source snippet."""

    chunk_id: str
    text: str
    page_start: int
    page_end: int
    source_file: str
    section_id: str
    section_number: str
    section_title: str
    parent_section_id: str | None
    parent_section_number: str | None
    parent_section_title: str | None
    order: int
    referenced_section_ids: list[str]
    source_type: str
    score: float | None = None
