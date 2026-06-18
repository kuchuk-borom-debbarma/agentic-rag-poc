import argparse
import sys

from agents import (
    AnswerAgent,
    ReflectionAgent,
    RouterAgent,
    SemanticSearchAgent,
    VerificationResult,
    VerifiedAnswer,
    VerifierAgent,
    EvidenceAgent,
    format_context,
)
from config import load_config
from graph_tools import GraphTools
from llm_client import OpenAICompatibleClient


MAX_BRANCH_REPAIRS = 1
MAX_FINAL_REPAIRS = 1


def print_trace(title, lines):
    print(f"\n[{title}]")
    for line in lines:
        print(line)


def print_sources(context_blocks):
    print("\nSources")
    for block in context_blocks:
        score = "n/a" if block.score is None else f"{block.score:.4f}"
        print(f"- [{block.source_id}] {section_label(block)}")
        print(f"  chunk={block.chunk_id} page={block.page_start} score={score}")


def section_label(item):
    section = "Front Matter" if item.section_number == "front_matter" else f"Section {item.section_number}"
    if item.section_title:
        section += f" - {item.section_title}"
    return section


def match_section_label(match):
    section_number = match.get("section_number")
    section = "Front Matter" if section_number == "front_matter" else f"Section {section_number}"
    if match.get("section_title"):
        section += f" - {match.get('section_title')}"
    return section


def describe_match(match):
    score = match.get("score")
    score_text = "n/a" if score is None else f"{score:.4f}"
    return [
        f"  - {match_section_label(match)}",
        f"    chunk={match.get('chunk_id')} page={match.get('page_start')} score={score_text}",
    ]


def make_clients(config):
    embedding_client = OpenAICompatibleClient(
        config.embedding_base_url,
        api_key=config.embedding_api_key,
        timeout=config.request_timeout_seconds,
    )
    chat_client = OpenAICompatibleClient(
        config.chat_base_url,
        api_key=config.chat_api_key,
        timeout=config.request_timeout_seconds,
        chat_options={
            "max_tokens": config.chat_max_tokens,
            "top_p": config.chat_top_p,
            "chat_template_kwargs": {"enable_thinking": config.chat_enable_thinking},
        },
    )
    return embedding_client, chat_client


def trace_config(config):
    print_trace(
        "Config",
        [
            f"neo4j_uri={config.neo4j_uri}",
            f"embedding_base_url={config.embedding_base_url}",
            f"embedding_model={config.embedding_model}",
            f"chat_base_url={config.chat_base_url}",
            f"chat_model={config.chat_model}",
        ],
    )


def trace_plan(title, plan):
    print_trace(
        title,
        [
            f"intent={plan.intent}",
            f"complexity={plan.complexity}",
            f"original_question={plan.original_question}",
            f"top_k={plan.top_k}",
            f"neighbors={plan.neighbors}",
            f"warnings={plan.warnings}",
            "retrieval_queries="
            + repr(
                [
                    {
                        "id": item.query_id,
                        "query": item.query,
                        "purpose": item.purpose,
                        "target_sections": item.target_sections,
                        "include_references": item.include_references,
                    }
                    for item in plan.retrieval_queries
                ]
            ),
        ],
    )


def trace_search_results(results, trace_hits):
    lines = []
    for result in results:
        lines.append(f"{result.retrieval_query.query_id}: matches={len(result.matches)} query={result.retrieval_query.query}")
        for match in result.matches[: min(trace_hits, len(result.matches))]:
            lines.extend(describe_match(match))
    print_trace(SemanticSearchAgent.name, lines)


def trace_evidence_bundle(evidence_bundle, trace_hits):
    lines = []
    for result in evidence_bundle.evidence_results:
        lines.append(f"{result.retrieval_query.query_id}: context_blocks={len(result.context_blocks)}")
        for block in result.context_blocks[: min(trace_hits, len(result.context_blocks))]:
            score = "n/a" if block.score is None else f"{block.score:.4f}"
            lines.append(f"  - [{block.source_id}] {section_label(block)}")
            lines.append(f"    chunk={block.chunk_id} page={block.page_start} score={score}")
    lines.append(f"merged_context_blocks={len(evidence_bundle.context_blocks)}")
    print_trace(EvidenceAgent.name, lines)


def trace_branch_answers(verified_branch_answers):
    print_trace(
        "SubanswerAgent",
        [
            (
                f"{item.retrieval_query.query_id}: citations={item.answer.citations} "
                f"valid={item.verification.valid} confidence={item.verification.confidence}"
            )
            for item in verified_branch_answers
        ],
    )
    print_trace(
        "VerifierAgent",
        [f"{item.retrieval_query.query_id}: issues={item.verification.issues}" for item in verified_branch_answers],
    )


def run_retrieval(plan, semantic_search, evidence_agent, args, trace_title):
    if args.trace:
        trace_plan(trace_title, plan)

    semantic_results = semantic_search.run(plan)
    if args.trace:
        trace_search_results(semantic_results, args.trace_hits)

    evidence_bundle = evidence_agent.run(plan, semantic_results)
    if args.trace:
        trace_evidence_bundle(evidence_bundle, args.trace_hits)

    return evidence_bundle


def answer_branches(plan, evidence_bundle, answer_agent, verifier, args):
    verified = []
    for evidence_result in evidence_bundle.evidence_results:
        answer = answer_agent.run_subanswer(
            plan.original_question,
            evidence_result.retrieval_query,
            evidence_result.context_blocks,
        )
        verification = verifier.run(
            evidence_result.retrieval_query.query,
            answer,
            evidence_result.context_blocks,
            use_llm=not args.skip_llm_verifier,
        )
        verified.append(
            VerifiedAnswer(
                retrieval_query=evidence_result.retrieval_query,
                answer=answer,
                verification=verification,
                context_blocks=evidence_result.context_blocks,
            )
        )

    if args.trace:
        trace_branch_answers(verified)
    return verified


def branch_issues(verified_branch_answers):
    issues = []
    for item in verified_branch_answers:
        if item.verification.valid:
            continue
        prefix = f"{item.retrieval_query.query_id} failed"
        if item.verification.issues:
            issues.extend(f"{prefix}: {issue}" for issue in item.verification.issues)
        else:
            issues.append(prefix)
    return issues


def repair_plan(plan, reflection_agent, issues):
    return reflection_agent.run(
        plan,
        VerificationResult(valid=False, confidence="low", issues=issues),
    )


def run_branch_flow(plan, semantic_search, evidence_agent, answer_agent, verifier, reflection_agent, args):
    for attempt in range(MAX_BRANCH_REPAIRS + 1):
        title = "RouterAgent" if attempt == 0 else "Branch Repair Plan"
        evidence_bundle = run_retrieval(plan, semantic_search, evidence_agent, args, title)

        if args.no_answer:
            return plan, evidence_bundle, []

        verified_branch_answers = answer_branches(plan, evidence_bundle, answer_agent, verifier, args)
        issues = branch_issues(verified_branch_answers)
        if not issues or attempt >= MAX_BRANCH_REPAIRS:
            return plan, evidence_bundle, verified_branch_answers

        if args.trace:
            print_trace("Orchestrator", ["Branch answer failed verification. Repairing retrieval before final answer."])
        plan = repair_plan(plan, reflection_agent, issues)

    return plan, evidence_bundle, verified_branch_answers


def synthesize_final(plan, evidence_bundle, verified_branch_answers, answer_agent, verifier, args):
    final_answer = answer_agent.run_final(plan.original_question, evidence_bundle.context_blocks, verified_branch_answers)
    final_verification = verifier.run(
        plan.original_question,
        final_answer,
        evidence_bundle.context_blocks,
        use_llm=not args.skip_llm_verifier,
    )

    if args.trace:
        print_trace("FinalAnswerAgent", [f"citations={final_answer.citations}"])
        print_trace(
            "FinalVerifierAgent",
            [
                f"valid={final_verification.valid}",
                f"confidence={final_verification.confidence}",
                f"issues={final_verification.issues}",
            ],
        )

    return final_answer, final_verification


def run(args):
    config = load_config()
    embedding_client, chat_client = make_clients(config)
    graph_tools = GraphTools(config.neo4j_uri, config.neo4j_auth)

    try:
        graph_tools.verify()
        if args.trace:
            trace_config(config)

        router = RouterAgent(chat_client, config.chat_model, max_queries=args.max_queries)
        semantic_search = SemanticSearchAgent(graph_tools, embedding_client, config.embedding_model)
        evidence_agent = EvidenceAgent(graph_tools)
        answer_agent = AnswerAgent(chat_client, config.chat_model)
        verifier = VerifierAgent(chat_client, config.chat_model)
        reflection_agent = ReflectionAgent(chat_client, config.chat_model)

        plan = router.run(args.question, args.top_k, args.neighbors)
        plan, evidence_bundle, verified_branch_answers = run_branch_flow(
            plan,
            semantic_search,
            evidence_agent,
            answer_agent,
            verifier,
            reflection_agent,
            args,
        )

        if args.no_answer:
            print_sources(evidence_bundle.context_blocks)
            if args.show_context:
                print("\nRetrieved Context\n")
                print(format_context(evidence_bundle.context_blocks))
            return 0

        final_answer = None
        final_verification = None
        for attempt in range(MAX_FINAL_REPAIRS + 1):
            final_answer, final_verification = synthesize_final(
                plan,
                evidence_bundle,
                verified_branch_answers,
                answer_agent,
                verifier,
                args,
            )
            if final_verification.valid or attempt >= MAX_FINAL_REPAIRS:
                break

            if args.trace:
                print_trace("Orchestrator", ["Final answer failed verification. Repairing retrieval and retrying final answer."])
            plan = reflection_agent.run(plan, final_verification)
            plan, evidence_bundle, verified_branch_answers = run_branch_flow(
                plan,
                semantic_search,
                evidence_agent,
                answer_agent,
                verifier,
                reflection_agent,
                args,
            )

        print_output(args, final_answer, final_verification, verified_branch_answers, evidence_bundle)
        return 0 if final_verification.valid else 2
    finally:
        graph_tools.close()


def print_output(args, final_answer, final_verification, verified_branch_answers, evidence_bundle):
    if args.show_branches:
        print("\nBranch Answers")
        for item in verified_branch_answers:
            print(f"\n{item.retrieval_query.query_id}: {item.retrieval_query.purpose}")
            print(item.answer.answer)
            print(f"verification={item.verification.valid} confidence={item.verification.confidence}")
            for issue in item.verification.issues:
                print(f"- {issue}")

    print("\nAnswer\n")
    print(final_answer.answer)
    print_sources(evidence_bundle.context_blocks)

    print("\nVerification")
    print(f"valid={final_verification.valid}")
    print(f"confidence={final_verification.confidence}")
    for issue in final_verification.issues:
        print(f"- {issue}")

    if args.show_context:
        print("\nRetrieved Context\n")
        print(format_context(evidence_bundle.context_blocks))


def parse_args():
    parser = argparse.ArgumentParser(description="Run the multi-agent query loop over the Neo4j RAG graph.")
    parser.add_argument("question", nargs="?", help="Question to ask against the ingested document graph")
    parser.add_argument("--top-k", type=int, default=8, help="Number of vector matches to retrieve per generated query")
    parser.add_argument("--neighbors", type=int, default=0, help="Initial neighbor chunks before/after each semantic match")
    parser.add_argument("--max-queries", type=int, default=5, help="Maximum router-generated retrieval queries")
    parser.add_argument("--trace", action="store_true", help="Show each agent's intermediate output")
    parser.add_argument("--trace-hits", type=int, default=3, help="Top matches/context blocks to show per trace stage")
    parser.add_argument("--show-context", action="store_true", help="Print assembled merged context")
    parser.add_argument("--show-branches", action="store_true", help="Print subanswers before the final answer")
    parser.add_argument("--no-answer", action="store_true", help="Only retrieve and print sources/context")
    parser.add_argument("--skip-llm-verifier", action="store_true", help="Use deterministic verifier checks only")
    args = parser.parse_args()
    if not args.question:
        parser.error("question is required")
    return args


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f"Query failed: {error}", file=sys.stderr)
        raise SystemExit(1)
