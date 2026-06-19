"""Agentic Query Planner (LLM Router).

Internal to the query bounded context. Not accessible from outside.
"""

import logging
from typing import List

from pydantic import BaseModel, Field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from assessment_app.services.query.public.models import QueryPlan, RetrievalQuery


logger = logging.getLogger(__name__)


class _RetrievalQuerySchema(BaseModel):
    query_id: str = Field(description="Unique ID, e.g., Q1")
    query: str = Field(description="The retrieval query string")
    purpose: str = Field(description="Why this query is needed")
    target_sections: List[str] = Field(description="Specific section numbers to target, if any")
    include_references: bool = Field(description="Whether to include referenced sections")


class _QueryPlanSchema(BaseModel):
    retrieval_queries: List[_RetrievalQuerySchema] = Field(description="The generated subqueries")


class QueryPlanner:
    """Agentic Query Planner (LLM Router).
    
    Deconstructs a user query into specific retrieval sub-queries optimized for vector search.
    """

    def __init__(self, chat_client: BaseChatModel) -> None:
        self._chat_client = chat_client
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_core.runnables import RunnableLambda
        import re

        def strip_think_block(message) -> str:
            text = message.content if hasattr(message, "content") else str(message)
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            return text.strip()

        self._parser = PydanticOutputParser(pydantic_object=_QueryPlanSchema)

        self._prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are a production RAG router. Create retrieval subqueries only. "
             "Do not answer the user. Break the query down into minimal, keyword-focused "
             "retrieval queries optimized specifically for vector similarity search. "
             "The contract is written in the second person ('you'/'your' for the customer, 'we'/'us' for the provider). "
             "Rephrase queries into the contract's perspective. "
             "Use contract wording and synonyms likely to appear in legal clauses. Examples: "
             "promise about security -> will implement reasonable appropriate measures secure Your Content; "
             "ownership rights -> obtain no rights Your Content licensors; "
             "term start end -> term commence Effective Date remain in effect terminated. "
             "Always include a representation of the original question as Q1.\n\n"
             "Ensure you return exactly the requested JSON format without any other conversational text.\n\n"
             "Respond ONLY with a JSON object in this exact format:\n"
             "{{\n"
             '  "retrieval_queries": [\n'
             "    {{\n"
             '      "query_id": "Q1",\n'
             '      "query": "The actual search query string",\n'
             '      "purpose": "Why this query is needed",\n'
             '      "target_sections": ["1.2", "4.1"],\n'
             '      "include_references": false\n'
             "    }}\n"
             "  ]\n"
             "}}"),
            ("human", "Original question:\n{query}\n\nDeconstruct this into subqueries.")
        ])
        
        self._chain = self._prompt | self._chat_client | RunnableLambda(strip_think_block) | self._parser

    def plan(self, query: str) -> QueryPlan:
        """Return a QueryPlan with one or more RetrievalQuery entries."""
        try:
            result = self._chain.invoke({
                "query": query
            })
            
            retrieval_queries = []
            for item in result.retrieval_queries:
                retrieval_queries.append(
                    RetrievalQuery(
                        query_id=item.query_id,
                        query=item.query,
                        purpose=item.purpose,
                        target_sections=item.target_sections,
                        include_references=item.include_references
                    )
                )
            
            if not retrieval_queries:
                raise ValueError("No retrieval queries returned by LLM")
                
            return QueryPlan(original_query=query, retrieval_queries=retrieval_queries)
            
        except Exception as e:
            logger.warning("LLM Query Planner failed, falling back to simple query: %s", e)
            return QueryPlan(
                original_query=query,
                retrieval_queries=[
                    RetrievalQuery(
                        query_id="Q1",
                        query=query,
                        purpose="fallback original question",
                        target_sections=[],
                        include_references=False,
                    )
                ]
            )
