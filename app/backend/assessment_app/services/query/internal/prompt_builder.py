"""Prompt builder helpers for the query service.

Internal to the query bounded context. Not accessible from outside.
"""

from assessment_app.services.query.public.models import SourceSnippet

NO_ANSWER_MESSAGE = "I could not find this in the AWS Customer Agreement."


def build_answer_messages(query: str, sources: list[SourceSnippet]) -> list[dict[str, str]]:
    """Build the chat messages list for the LLM answer request.

    Formats sources as numbered context blocks so the model can cite them with [S1] labels.
    """
    context = "\n\n".join(
        (
            f"[S{index}] {source.section_label} | page {source.page_start} | "
            f"chunk={source.chunk_id} | source={source.source_type}\n{source.text}"
        )
        for index, source in enumerate(sources, start=1)
    )
    return [
        {
            "role": "system",
            "content": (
                "You are an expert on the AWS Customer Agreement. "
                "Use ONLY the provided context to answer the question. "
                f"If the answer is not present, reply exactly: {NO_ANSWER_MESSAGE} "
                "CRITICAL REQUIREMENTS:\n"
                "1. Be extremely concise and compact.\n"
                "2. Provide direct answers without any conversational filler or yapping.\n"
                "3. Cite your sources using labels like [S1]."
            ),
        },
        {
            "role": "user",
            "content": f"Question:\n{query}\n\nContext:\n{context}\n\nAnswer:",
        },
    ]


def answer_found(answer: str) -> bool:
    """Return True if the answer does not contain the NO_ANSWER_MESSAGE sentinel."""
    return NO_ANSWER_MESSAGE.lower() not in answer.strip().lower()
