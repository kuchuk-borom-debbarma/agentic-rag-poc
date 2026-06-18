# Evaluation

## Purpose

- Owns durable documentation for benchmark RAG evaluation flow and metric categories.

## Ownership

- `evaluation-flow.md` defines the benchmark evaluation request flow, metric groups, current limits, and future scaling path.

## Local Contracts

- Evaluation docs must match backend evaluation code and frontend evaluation UI.
- Keep evidence metrics explicit: what is measured, why it matters, and what the metric cannot prove yet.
- Do not store generated evaluation results here.

## Work Guidance

- Update this folder when evaluation categories, thresholds, route shape, or UI behavior changes.
- Keep docs practical enough for assessment walkthrough.

## Verification

- Backend tests: `pytest` from `app/backend/`.
- Frontend build: `npm run build` from `app/frontend/`.

## Child DOX Index

- No child AGENTS.md files.
