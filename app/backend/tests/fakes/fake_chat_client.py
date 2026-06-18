"""Fake ChatClient for unit tests.

Satisfies query.internal.ports.ChatClient.
"""


class FakeChatClient:
    """Returns a configurable canned answer."""

    def __init__(self, answer: str = "This is a test answer.") -> None:
        self._answer = answer

    def answer(self, messages: list[dict[str, str]]) -> str:
        return self._answer
