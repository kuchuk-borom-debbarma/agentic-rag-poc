"""Public errors for the query bounded context.

Services raise these. Routes and exception handlers convert them to HTTP responses.
"""


class QueryError(Exception):
    """Base error for the query service."""


class NotIngestedError(QueryError):
    """Raised when a query is attempted before a document index exists."""

    def __init__(self) -> None:
        super().__init__("No document index exists yet.")
