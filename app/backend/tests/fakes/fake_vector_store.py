"""Fake VectorStore implementations for unit tests.

FakeQueryVectorStore satisfies services.query.internal.ports.VectorStore.
"""

from assessment_app.services.query.public.models import SourceSnippet, VerificationResult


class FakeSemanticStore:
    def __init__(self, snippets: list[SourceSnippet] | None = None, chunk_count: int = 1) -> None:
        self._snippets = snippets or []
        self._chunk_count = chunk_count

    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        return [(snippet.chunk_id, 0.9) for snippet in self._snippets[:top_k]]

    def count(self) -> int:
        return self._chunk_count


class FakeGraphStore:
    def __init__(self, snippets: list[SourceSnippet] | None = None) -> None:
        self._snippets = {s.chunk_id: s for s in (snippets or [])}

    def get_chunk(self, chunk_id: str) -> SourceSnippet | None:
        return self._snippets.get(chunk_id)

    def get_neighbors(self, chunk_ids: list[str], neighbors: int = 1) -> list[SourceSnippet]:
        return []

    def get_section_chunks(self, section_numbers: list[str]) -> list[SourceSnippet]:
        return []

    def get_referenced_sections(self, chunk_ids: list[str], limit: int = 2) -> list[SourceSnippet]:
        return []


class FakeEvidenceVerifier:
    def __init__(self, is_sufficient: bool = True):
        self.is_sufficient = is_sufficient

    def verify(self, query: str, evidence: list[SourceSnippet]) -> VerificationResult:
        return VerificationResult(
            is_sufficient=self.is_sufficient,
            needs_references=False,
            needs_parents=False,
            needs_children=False,
            needs_neighbors=False,
            issues=[]
        )
