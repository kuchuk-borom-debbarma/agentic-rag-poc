"""Public contract for the query bounded context.

Only this file (and models.py / errors.py) may be imported by routes, other services, or config.
"""

import typing
from typing import Protocol

from assessment_app.services.query.public.models import AskResult


class QueryService(Protocol):
    """Public contract for answering questions against the ingested document."""

    def ask(
        self,
        query: str,
        top_k: int | None = None,
        max_loops: int = 4,
        log_query: bool = True,
    ) -> typing.Iterable[dict[str, typing.Any]]:
        """Search the vector store and generate a grounded answer.

        Args:
            query: The user question.
            top_k: Override the default number of retrieved chunks.
            log_query: Whether to persist this query in the analytics log.

        Returns:
            AskResult containing answer, found flag, sources, and latency.
        Raises:
            NotIngestedError if no document has been ingested yet.
        """
        ...
