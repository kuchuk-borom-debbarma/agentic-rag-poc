import re
from dataclasses import dataclass

try:
    from graph_tools import rows_to_context_blocks
    from llm_client import parse_json_object
except ImportError:
    from .graph_tools import rows_to_context_blocks
    from .llm_client import parse_json_object


SECTION_RE = re.compile(r"\bsection\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE)
SOURCE_RE = re.compile(r"\[(S\d+)\]")


@dataclass(frozen=True)
class RetrievalQuery:
    query_id: str
    query: str
    purpose: str
    target_sections: list[str]
    include_references: bool


@dataclass(frozen=True)
class RoutePlan:
    intent: str
    complexity: str
    original_question: str
    retrieval_queries: list[RetrievalQuery]
    top_k: int
    neighbors: int
    warnings: list[str]


@dataclass(frozen=True)
class SemanticSearchResult:
    retrieval_query: RetrievalQuery
    matches: list[dict]


@dataclass(frozen=True)
class EvidenceResult:
    retrieval_query: RetrievalQuery
    matches: list[dict]
    context_blocks: list


@dataclass(frozen=True)
class EvidenceBundle:
    evidence_results: list[EvidenceResult]
    context_blocks: list


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    citations: list[str]


@dataclass(frozen=True)
class VerifiedAnswer:
    retrieval_query: RetrievalQuery
    answer: AnswerResult
    verification: "VerificationResult"
    context_blocks: list


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    confidence: str
    issues: list[str]


class RouterAgent:
    name = "RouterAgent"

    def __init__(self, chat_client=None, chat_model=None, max_queries=5):
        self.chat_client = chat_client
        self.chat_model = chat_model
        self.max_queries = max_queries

    def run(self, question, top_k, neighbors):
        heuristic_plan = self._heuristic_route(question, top_k, neighbors, warnings=[])
        if heuristic_plan.complexity == "simple":
            return heuristic_plan

        if self.chat_client and self.chat_model:
            try:
                return self._llm_route(question, top_k, neighbors)
            except Exception as error:
                return self._heuristic_route(
                    question,
                    top_k,
                    neighbors,
                    warnings=[f"LLM router failed; used heuristic router: {error}"],
                )
        return self._heuristic_route(question, top_k, neighbors, warnings=[])

    def _llm_route(self, question, top_k, neighbors):
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a production RAG router. Create retrieval subqueries only. "
                    "Do not answer the user. Do not add concepts not present in the original question. "
                    "Each subquery must preserve meaning while isolating one branch or nearby phrasing. "
                    "Always include the original question as Q1. Return JSON only with this shape: "
                    '{"intent":"semantic_search|section_lookup|comparison|compound",'
                    '"complexity":"simple|compound|complex",'
                    '"neighbors":1,'
                    '"warnings":[],'
                    '"retrieval_queries":[{"query_id":"Q1","query":"...",'
                    '"purpose":"...","target_sections":[],"include_references":false}]}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original question:\n{question}\n\n"
                    f"Max retrieval queries: {self.max_queries}\n"
                    "Use multiple queries only when the question has multiple topics, comparisons, "
                    "conditions, long jumps, or legal/contract concepts that need separate evidence."
                ),
            },
        ]
        raw = self.chat_client.chat(self.chat_model, messages, temperature=0)
        payload = parse_json_object(raw)
        queries = self._coerce_queries(question, payload.get("retrieval_queries") or [])
        
        return RoutePlan(
            intent=payload.get("intent") or self._intent_for(question),
            complexity=payload.get("complexity") or self._complexity_for(question, queries),
            original_question=question.strip(),
            retrieval_queries=queries,
            top_k=top_k,
            neighbors=neighbors,
            warnings=list(payload.get("warnings") or []),
        )

    def _heuristic_route(self, question, top_k, neighbors, warnings):
        clauses = self._split_question(question)
        queries = [
            RetrievalQuery(
                query_id="Q1",
                query=question.strip(),
                purpose="original question",
                target_sections=SECTION_RE.findall(question),
                include_references=self._needs_references(question),
            )
        ]

        for clause in clauses:
            if len(queries) >= self.max_queries:
                break
            if clause.lower() == question.strip().lower():
                continue
            queries.append(
                RetrievalQuery(
                    query_id=f"Q{len(queries) + 1}",
                    query=clause,
                    purpose="isolated branch from original question",
                    target_sections=SECTION_RE.findall(clause),
                    include_references=self._needs_references(clause),
                )
            )

        return RoutePlan(
            intent=self._intent_for(question),
            complexity=self._complexity_for(question, queries),
            original_question=question.strip(),
            retrieval_queries=queries,
            top_k=top_k,
            neighbors=neighbors,
            warnings=warnings,
        )

    def _coerce_queries(self, question, raw_queries):
        queries = []
        seen = set()

        orig_item = next((item for item in raw_queries if str(item.get("query", "")).strip().lower() == question.strip().lower()), None)
        
        if orig_item:
            target_sections = orig_item.get("target_sections")
            if not isinstance(target_sections, list):
                target_sections = SECTION_RE.findall(question)
            inc_ref = orig_item.get("include_references")
            if inc_ref is None:
                inc_ref = self._needs_references(question)
            queries.append(
                RetrievalQuery(
                    query_id=orig_item.get("query_id") or "Q1",
                    query=question.strip(),
                    purpose=str(orig_item.get("purpose") or "original question"),
                    target_sections=[str(s) for s in target_sections],
                    include_references=bool(inc_ref)
                )
            )
        else:
            queries.append(
                RetrievalQuery(
                    query_id="Q1",
                    query=question.strip(),
                    purpose="original question",
                    target_sections=SECTION_RE.findall(question),
                    include_references=self._needs_references(question),
                )
            )
            
        seen.add(question.strip().lower())

        for item in raw_queries:
            if len(queries) >= self.max_queries:
                break
            query = str(item.get("query", "")).strip()
            if not query or query.lower() in seen:
                continue
            query_id = str(item.get("query_id") or f"Q{len(queries) + 1}")
            target_sections = item.get("target_sections")
            if not isinstance(target_sections, list):
                target_sections = SECTION_RE.findall(query)
            
            inc_ref = item.get("include_references")
            if inc_ref is None:
                inc_ref = self._needs_references(query)
                
            queries.append(
                RetrievalQuery(
                    query_id=query_id,
                    query=query,
                    purpose=str(item.get("purpose") or "retrieval branch"),
                    target_sections=[str(section) for section in target_sections],
                    include_references=bool(inc_ref),
                )
            )
            seen.add(query.lower())

        return queries

    def _split_question(self, question):
        normalized = re.sub(r"\s+", " ", question.strip())
        parts = re.split(r"\s+(?:and|also|plus|as well as|while|but|versus|vs\.?)\s+", normalized, flags=re.I)
        return [part.strip(" ,.;?") for part in parts if len(part.strip(" ,.;?")) >= 12]

    def _intent_for(self, question):
        lowered = question.lower()
        if SECTION_RE.search(question):
            return "section_lookup"
        if any(word in lowered for word in ["compare", "difference", "versus", " vs "]):
            return "comparison"
        if len(self._split_question(question)) > 1:
            return "compound"
        return "semantic_search"

    def _complexity_for(self, question, queries):
        if len(queries) >= 4:
            return "complex"
        if len(queries) > 1 or len(question.split()) > 18:
            return "compound"
        return "simple"

    def _needs_references(self, text):
        lowered = text.lower()
        return any(word in lowered for word in ["refer", "reference", "linked", "related", "depend", "affect"])


class SemanticSearchAgent:
    name = "SemanticSearchAgent"

    def __init__(self, graph_tools, embedding_client, embedding_model):
        self.graph_tools = graph_tools
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model

    def run(self, plan):
        return [self._run_one(plan, retrieval_query) for retrieval_query in plan.retrieval_queries]

    def _run_one(self, plan, retrieval_query):
        query_vector = self.embedding_client.embed(self.embedding_model, retrieval_query.query)
        matches = self.graph_tools.semantic_search(query_vector, plan.top_k)
        return SemanticSearchResult(retrieval_query=retrieval_query, matches=matches)


class EvidenceAgent:
    name = "EvidenceAgent"

    def __init__(self, graph_tools):
        self.graph_tools = graph_tools

    def run(self, plan, semantic_results):
        evidence_results = [self._run_one(plan, result) for result in semantic_results]
        all_rows = []
        for result in evidence_results:
            all_rows.extend(_context_blocks_to_rows(result.context_blocks))
        return EvidenceBundle(evidence_results=evidence_results, context_blocks=rows_to_context_blocks(all_rows))

    def _run_one(self, plan, semantic_result):
        retrieval_query = semantic_result.retrieval_query
        exact_section_rows = self.graph_tools.get_section_chunks(retrieval_query.target_sections)
        rows = list(exact_section_rows) + list(semantic_result.matches)

        if plan.neighbors:
            orders = [row["order"] for row in semantic_result.matches]
            rows.extend(self.graph_tools.get_neighbors(orders, before=plan.neighbors, after=plan.neighbors))

        if retrieval_query.include_references:
            chunk_ids = [row["chunk_id"] for row in rows]
            rows.extend(self.graph_tools.get_referenced_sections(chunk_ids))

        return EvidenceResult(
            retrieval_query=retrieval_query,
            matches=semantic_result.matches,
            context_blocks=rows_to_context_blocks(rows),
        )


class AnswerAgent:
    name = "AnswerAgent"

    def __init__(self, chat_client, chat_model):
        self.chat_client = chat_client
        self.chat_model = chat_model

    def run_subanswer(self, original_question, retrieval_query, context_blocks):
        question = (
            f"Original question:\n{original_question}\n\n"
            f"Retrieval branch ({retrieval_query.query_id}):\n{retrieval_query.query}\n\n"
            f"Branch purpose:\n{retrieval_query.purpose}"
        )
        return self._answer(question, context_blocks, mode="branch")

    def run_final(self, original_question, context_blocks, verified_answers):
        subanswers = "\n\n".join(
            (
                f"{item.retrieval_query.query_id} ({item.retrieval_query.purpose}) "
                f"verification={item.verification.valid}, confidence={item.verification.confidence}\n"
                f"{item.answer.answer}"
            )
            for item in verified_answers
        )
        context = format_context(context_blocks)
        messages = [
            {
                "role": "system",
                "content": (
                    "You synthesize the final answer to the original user question. "
                    "Use strictly only verified branch answers and retrieved context. "
                    "Do not make assumptions, guess, or use any outside knowledge. "
                    "Everything must be derived strictly from the provided source material. "
                    "Cite every factual claim with source ids like [S1]. "
                    "If evidence is missing or a branch failed verification, state what is not supported."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original question:\n{original_question}\n\n"
                    f"Verified branch answers:\n{subanswers}\n\n"
                    f"Retrieved context:\n{context}\n\n"
                    "Final answer with citations:"
                ),
            },
        ]
        answer = self.chat_client.chat(self.chat_model, messages, temperature=0.1)
        return AnswerResult(answer=answer, citations=_citations(answer))

    def _answer(self, question, context_blocks, mode):
        if not context_blocks:
            return AnswerResult(
                answer="I could not find relevant source material for this retrieval branch.",
                citations=[],
            )

        context = format_context(context_blocks)
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a strictly grounded RAG {mode} answer agent. "
                    "Answer using strictly only the provided context. "
                    "Do not make assumptions, guess, or use any outside knowledge. "
                    "Everything must be derived strictly from the provided source material. "
                    "Cite every factual claim with source ids like [S1]. "
                    "If context is insufficient, state what is not found in the source material."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nContext:\n{context}\n\nAnswer with citations:",
            },
        ]
        answer = self.chat_client.chat(self.chat_model, messages, temperature=0.1)
        return AnswerResult(answer=answer, citations=_citations(answer))



class ReflectionAgent:
    name = "ReflectionAgent"

    def __init__(self, chat_client, chat_model):
        self.chat_client = chat_client
        self.chat_model = chat_model

    def run(self, plan: "RoutePlan", verification_result: "VerificationResult") -> "RoutePlan":
        issues_text = "\n".join(f"- {issue}" for issue in verification_result.issues)
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict RAG Reflection Agent. "
                    "The previous search failed to find enough information to pass verification. "
                    "Your job is to read the verification failures and create a new search plan.\n\n"
                    "Rules:\n"
                    "1. Write 1 or 2 NEW highly specific search queries to find the missing facts (e.g. searching for exact definitions or edge cases).\n"
                    "2. If the issues mention missing surrounding context, set 'neighbors' to 1 or 2.\n"
                    "3. If the issues mention missing linked sections, set 'include_references' to true.\n\n"
                    "Return strictly JSON only: {\"neighbors\": <int>, \"include_references\": <bool>, \"new_queries\": [{\"query\": \"<string>\", \"purpose\": \"<string>\"}], \"reasoning\": \"<string>\"}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original Question:\n{plan.original_question}\n\n"
                    f"Verification Issues:\n{issues_text}\n\n"
                    "How should we update the search plan?"
                ),
            },
        ]
        
        try:
            payload = parse_json_object(self.chat_client.chat(self.chat_model, messages, temperature=0))
            new_neighbors = int(payload.get("neighbors", plan.neighbors))
            new_refs = bool(payload.get("include_references", False))
            
            queries = []
            for q in plan.retrieval_queries:
                queries.append(RetrievalQuery(
                    query_id=q.query_id,
                    query=q.query,
                    purpose=q.purpose,
                    target_sections=q.target_sections,
                    include_references=q.include_references or new_refs
                ))
                
            new_raw_queries = payload.get("new_queries") or []
            for idx, item in enumerate(new_raw_queries):
                query = str(item.get("query", "")).strip()
                if not query:
                    continue
                queries.append(RetrievalQuery(
                    query_id=f"R{idx+1}",
                    query=query,
                    purpose="reflection: " + str(item.get("purpose", "")),
                    target_sections=[],
                    include_references=new_refs
                ))
                
            return RoutePlan(
                intent=plan.intent,
                complexity=plan.complexity,
                original_question=plan.original_question,
                retrieval_queries=queries,
                top_k=plan.top_k,
                neighbors=max(plan.neighbors, new_neighbors),
                warnings=plan.warnings + [f"Feedback applied: neighbors={new_neighbors}, new_queries={len(new_raw_queries)}. Reasoning: {payload.get('reasoning')}"]
            )
        except Exception as error:
            queries = [
                RetrievalQuery(
                    query_id=q.query_id,
                    query=q.query,
                    purpose=q.purpose,
                    target_sections=q.target_sections,
                    include_references=True
                ) for q in plan.retrieval_queries
            ]
            return RoutePlan(
                intent=plan.intent,
                complexity=plan.complexity,
                original_question=plan.original_question,
                retrieval_queries=queries,
                top_k=plan.top_k,
                neighbors=max(plan.neighbors, 1),
                warnings=plan.warnings + [f"Reflection fallback triggered due to error: {error}"]
            )

class VerifierAgent:
    name = "VerifierAgent"

    def __init__(self, chat_client=None, chat_model=None):
        self.chat_client = chat_client
        self.chat_model = chat_model

    def run(self, question, answer_result, context_blocks, use_llm=True):
        available = {block.source_id for block in context_blocks}
        cited = set(answer_result.citations)
        issues = []

        if not answer_result.answer.strip():
            issues.append("answer is empty")
        if not cited and "could not find" not in answer_result.answer.lower() and "not found" not in answer_result.answer.lower():
            issues.append("answer has no citations")
        unknown = sorted(cited - available)
        if unknown:
            issues.append(f"answer cites unknown sources: {', '.join(unknown)}")

        if use_llm and self.chat_client and self.chat_model and context_blocks and not unknown:
            issues.extend(self._llm_support_check(question, answer_result.answer, context_blocks))

        if issues:
            return VerificationResult(valid=False, confidence="low", issues=issues)
        confidence = "high" if cited else "medium"
        return VerificationResult(valid=True, confidence=confidence, issues=[])

    def _llm_support_check(self, question, answer, context_blocks):
        context = format_context(context_blocks)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict RAG verifier. Return JSON only: "
                    '{"supported": true|false, "issues": ["..."]}. '
                    "Mark unsupported if answer contains assumptions, guesses, or claims not explicitly grounded in context."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nContext:\n{context}\n\nAnswer:\n{answer}",
            },
        ]
        try:
            raw = self.chat_client.chat(self.chat_model, messages, temperature=0)
            payload = parse_json_object(raw)
        except Exception as error:
            return [f"LLM verifier failed: {error}"]

        if payload.get("supported") is True:
            return []
        return payload.get("issues") or ["LLM verifier marked answer unsupported"]


def format_context(context_blocks):
    parts = []
    for block in context_blocks:
        score = "" if block.score is None else f" | score {block.score:.4f}"
        parts.append(f"[{block.source_id}] {block.label}{score}\n{block.text}")
    return "\n\n".join(parts)


def _citations(answer):
    return sorted(set(SOURCE_RE.findall(answer)), key=lambda item: int(item[1:]))


def _context_blocks_to_rows(context_blocks):
    rows = []
    for block in context_blocks:
        rows.append(
            {
                "embedding_id": block.embedding_id,
                "chunk_id": block.chunk_id,
                "section_id": block.section_id,
                "section_number": block.section_number,
                "section_title": block.section_title,
                "page_start": block.page_start,
                "page_end": block.page_end,
                "order": block.order,
                "text": block.text,
                "score": block.score,
            }
        )
    return rows
