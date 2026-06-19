"""Self-reflective verifier for evidence checking.

Internal to the query bounded context.
"""

import logging
from typing import List

from pydantic import BaseModel, Field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from assessment_app.services.query.public.models import SourceSnippet, VerificationResult


logger = logging.getLogger(__name__)


class _VerificationResultSchema(BaseModel):
    is_sufficient: bool = Field(description="Is the evidence sufficient to answer the query?")
    needs_references: bool = Field(description="Are there referenced sections missing?")
    needs_parents: bool = Field(description="Is the context lacking parent information?")
    needs_children: bool = Field(description="Is the context lacking child sub-point details?")
    needs_neighbors: bool = Field(description="Does the text cut off and need neighbors?")
    issues: List[str] = Field(description="Specific missing information if not sufficient")


class LLMEvidenceVerifier:
    """Verifies whether the retrieved evidence is sufficient to answer the query."""

    def __init__(self, chat_client: BaseChatModel) -> None:
        self._chat_client = chat_client
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_core.runnables import RunnableLambda
        import re

        def strip_think_block(message) -> str:
            text = message.content if hasattr(message, "content") else str(message)
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            return text.strip()

        self._parser = PydanticOutputParser(pydantic_object=_VerificationResultSchema)
        
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a strict verification system evaluating retrieved document chunks. "
                       "Your task is to determine if the provided Evidence contains sufficient information "
                       "to directly and accurately answer the exact User Query. Related evidence is not "
                       "sufficient unless it contains the requested obligation, right, deadline, definition, "
                       "or process in direct form.\n\n"
                       "Rules for expansion if the evidence is insufficient:\n"
                       "- If the text mentions a referenced section that isn't provided, set needs_references=true.\n"
                       "- If the text seems like a sub-point and lacks the overarching definition or section context, set needs_parents=true.\n"
                       "- If the text is a high-level summary and lacks the detailed bullet points below it, set needs_children=true.\n"
                       "- If the text cuts off abruptly or lacks surrounding context, set needs_neighbors=true.\n\n"
                       "Ensure you return exactly the requested JSON format without any other conversational text.\n\n"
                       "Respond ONLY with a JSON object in this exact format:\n"
                       "{{\n"
                       '  "is_sufficient": false,\n'
                       '  "needs_references": false,\n'
                       '  "needs_parents": false,\n'
                       '  "needs_children": false,\n'
                       '  "needs_neighbors": false,\n'
                       '  "issues": ["List specific missing information here"]\n'
                       "}}"),
            ("human", "User Query: \"{query}\"\n\nEvidence:\n{evidence_text}")
        ])
        self._chain = self._prompt | self._chat_client | RunnableLambda(strip_think_block) | self._parser

    def verify(self, query: str, evidence: list[SourceSnippet]) -> VerificationResult:
        """Call the ChatClient to evaluate the evidence and guide topological expansion."""
        if not evidence:
            return VerificationResult(
                is_sufficient=False,
                needs_references=False,
                needs_parents=False,
                needs_children=False,
                needs_neighbors=False,
                issues=["No evidence provided"],
            )

        evidence_text = "\n\n".join(
            f"[{snippet.section_label}]\n{snippet.text}"
            for snippet in evidence
        )

        try:
            result = self._chain.invoke({
                "query": query,
                "evidence_text": evidence_text
            })
            
            return VerificationResult(
                is_sufficient=result.is_sufficient,
                needs_references=result.needs_references,
                needs_parents=result.needs_parents,
                needs_children=result.needs_children,
                needs_neighbors=result.needs_neighbors,
                issues=result.issues,
            )
        except Exception as e:
            logger.warning("LLMEvidenceVerifier failed, failing closed: %s", e)
            return VerificationResult(
                is_sufficient=False,
                needs_references=False,
                needs_parents=True,
                needs_children=True,
                needs_neighbors=False,
                issues=["Verifier failed; evidence treated as insufficient."],
            )
