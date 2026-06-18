"""Fake EmbeddingClient for unit tests."""


class FakeEmbeddingClient:
    """Returns constant zero-vectors. Sufficient for testing orchestration."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0]
