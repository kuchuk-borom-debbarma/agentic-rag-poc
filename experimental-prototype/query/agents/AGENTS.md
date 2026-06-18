# Query Agents

## Purpose

- Owns the task-specific query agents used to test grounded question answering over the Neo4j document graph.

## Ownership

- `query_cli.py` provides the local command-line entry point.
- `config.py` loads Neo4j, embedding, and chat model settings from environment files.
- `llm_client.py` owns OpenAI-compatible embedding and chat HTTP calls.
- `graph_tools.py` owns Neo4j retrieval tools.
- `agents.py` owns the Router, Semantic Search, Evidence, Reflection, Subanswer, Verifier, Final Answer, and Final Verifier stages.
- `query_cli.py` orchestrates branch-level repair before final synthesis and final repair before output.
- `questions.txt` owns manual AWS Customer Agreement query evaluation questions with expected answers and supporting sections.

## Local Contracts

- Keep agents small and task-specific: route, search, collect evidence, answer branches, verify branches, repair failed branches, synthesize, verify final answer.
- Keep tool calls explicit and inspectable through CLI trace output.
- Do not let generated answers use evidence outside retrieved context.
- Keep Neo4j and model connection settings environment-driven.

## Work Guidance

- Prefer deterministic routing and verification checks where practical.
- Keep CLI output useful for testing retrieval quality, not optimized for a final user app.
- Keep `questions.txt` ordered from simple lookup to complex edge cases.
- Avoid adding a web server here until the query loop is proven.

## Verification

- Run `venv/bin/python query/agents/query_cli.py --help` after CLI changes.
- When Neo4j and the model backend are running, run `venv/bin/python query/agents/query_cli.py "What are customer responsibilities?" --trace --show-branches`.

## Child DOX Index

- No child AGENTS.md files.
