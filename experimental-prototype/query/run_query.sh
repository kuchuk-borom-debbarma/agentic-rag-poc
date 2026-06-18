#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"
PYTHON="$ROOT_DIR/../../venv/bin/python"
COMPOSE_DIR="$ROOT_DIR/step 2/substep1_infrastructure"
QUERY_CLI="$ROOT_DIR/agents/query_cli.py"
AGENT_ENV="$ROOT_DIR/agents/.env"

START_NEO4J=1
CHECK_HEALTH=1
INTERACTIVE=0
CLI_ARGS=()

step() {
  echo
  echo "$1"
}

usage() {
  cat <<'EOF'
Usage:
  ./run_query.sh "question" [query_cli flags]
  ./run_query.sh --interactive

Examples:
  ./run_query.sh "What are customer responsibilities?"
  ./run_query.sh "What are customer responsibilities and what happens to customer content?" --show-context
  ./run_query.sh --no-start "Compare customer responsibilities and AWS suspension rights" --max-queries 4
  ./run_query.sh -i --no-start

Script flags:
  --no-start       Do not start Neo4j Docker Compose.
  --no-health      Skip Neo4j/Ollama health checks.
  -i, --interactive
                   Prompt for query options and run one or more queries.
  -h, --help       Show this help.

Default query flags added by this script:
  --trace --show-branches

Any other flags are passed to query/agents/query_cli.py.
EOF
}

ask_default() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "$prompt [$default]: " value
  printf '%s' "${value:-$default}"
}

ask_yes_no() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "$prompt [$default]: " value
  value="${value:-$default}"
  case "$value" in
    y|Y|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

load_agent_env() {
  if [[ -f "$AGENT_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$AGENT_ENV"
    set +a
  fi
}

wait_for_neo4j() {
  "$PYTHON" - <<'PY'
import os
import time
from neo4j import GraphDatabase

uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
user = os.environ.get("NEO4J_USER", "neo4j")
password = os.environ.get("NEO4J_PASSWORD", "password123")
deadline = time.time() + 60
last_error = None

while time.time() < deadline:
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        print(f"Neo4j ready at {uri}")
        raise SystemExit(0)
    except Exception as error:
        last_error = error
        time.sleep(2)

raise SystemExit(f"Neo4j did not become ready within 60s: {last_error}")
PY
}

check_models() {
  "$PYTHON" - <<'PY'
from query.agents.config import load_config
from query.agents.llm_client import OpenAICompatibleClient

config = load_config()
embedding = OpenAICompatibleClient(
    config.embedding_base_url,
    api_key=config.embedding_api_key,
    timeout=config.request_timeout_seconds,
)
chat = OpenAICompatibleClient(
    config.chat_base_url,
    api_key=config.chat_api_key,
    timeout=config.request_timeout_seconds,
    chat_options={
        "max_tokens": 32,
        "top_p": config.chat_top_p,
        "chat_template_kwargs": {"enable_thinking": False},
    },
)

vector = embedding.embed(config.embedding_model, "health check")
reply = chat.chat(
    config.chat_model,
    [{"role": "user", "content": "Reply with exactly: ok"}],
    temperature=0,
)

print(f"Embedding ready: {config.embedding_model} dim={len(vector)}")
print(f"Chat ready: {config.chat_model} reply={reply[:40].strip()}")
PY
}

run_interactive_queries() {
  while true; do
    echo
    read -r -p "Question: " question
    if [[ -z "$question" ]]; then
      echo "Question required."
      continue
    fi

    top_k="$(ask_default "Top K per retrieval query" "8")"
    neighbors="$(ask_default "Neighbor chunks before/after" "1")"
    max_queries="$(ask_default "Max router queries" "5")"
    trace_hits="$(ask_default "Trace hits per stage" "5")"

    args=(
      "$question"
      --top-k "$top_k"
      --neighbors "$neighbors"
      --max-queries "$max_queries"
      --trace-hits "$trace_hits"
    )

    if ask_yes_no "Show full merged context?" "n"; then
      args+=(--show-context)
    fi

    if ask_yes_no "Retrieval only, no answer?" "n"; then
      args+=(--no-answer)
    fi

    if ask_yes_no "Skip LLM verifier?" "n"; then
      args+=(--skip-llm-verifier)
    fi

    echo
    echo "Running:"
    printf '  %q' "$PYTHON" "$QUERY_CLI" "${args[@]}" --trace --show-branches
    echo

    "$PYTHON" "$QUERY_CLI" "${args[@]}" --trace --show-branches

    if ! ask_yes_no "Run another query?" "n"; then
      break
    fi
  done
}

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --no-start)
      START_NEO4J=0
      shift
      ;;
    --no-health)
      CHECK_HEALTH=0
      shift
      ;;
    -i|--interactive)
      INTERACTIVE=1
      shift
      ;;
    *)
      CLI_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#CLI_ARGS[@]} -eq 0 && "$INTERACTIVE" -eq 0 ]]; then
  usage
  exit 2
fi

load_agent_env

export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

if [[ "$START_NEO4J" -eq 1 ]]; then
  step "[1/4] Starting Neo4j"
  cd "$COMPOSE_DIR"
  compose_cmd up -d
  cd "$ROOT_DIR"
else
  step "[1/4] Skipping Neo4j start"
fi

if [[ "$CHECK_HEALTH" -eq 1 ]]; then
  step "[2/4] Checking Neo4j"
  wait_for_neo4j

  step "[3/4] Checking Ollama models"
  check_models
else
  step "[2/4] Skipping health checks"
fi

step "[4/4] Running query agents"
if [[ "$INTERACTIVE" -eq 1 ]]; then
  run_interactive_queries
else
  "$PYTHON" "$QUERY_CLI" "${CLI_ARGS[@]}" --trace --show-branches
fi
