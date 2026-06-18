#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT_DIR/../../venv/bin/python"
COMPOSE_DIR="$ROOT_DIR/step 2/substep1_infrastructure"
STEP1_SCRIPT="$ROOT_DIR/step 1/document_processor.py"
INGEST_SCRIPT="$ROOT_DIR/step 2/substep2_graph_ingestion/ingest_parents.py"
EMBED_SCRIPT="$ROOT_DIR/step 2/substep3_vector_embedding/embed_children.py"
CHECK_SCRIPT="$ROOT_DIR/check_graph.py"

step() {
  echo
  echo "$1"
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

step "[1/8] Starting Neo4j"
cd "$COMPOSE_DIR"
compose_cmd up -d
cd "$ROOT_DIR"

step "[2/8] Waiting for Neo4j health"
"$PYTHON" - <<'PY'
import time
from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
auth = ("neo4j", "password123")
deadline = time.time() + 60
last_error = None
while time.time() < deadline:
    try:
        driver = GraphDatabase.driver(uri, auth=auth)
        driver.verify_connectivity()
        driver.close()
        print("[2/8] Neo4j ready")
        raise SystemExit(0)
    except Exception as error:
        last_error = error
        time.sleep(2)
raise SystemExit(f"Neo4j did not become ready within 60s: {last_error}")
PY

step "[3/8] Building document graph JSON"
"$PYTHON" "$STEP1_SCRIPT"

step "[4/8] Validating graph invariants"
"$PYTHON" "$STEP1_SCRIPT" --validate-only

step "[5/8] Ingesting Document/Section/Chunk graph"
"$PYTHON" "$INGEST_SCRIPT"

step "[6/8] Checking embedding backend health"
"$PYTHON" "$EMBED_SCRIPT" --health-only

step "[7/8] Vectorizing chunks"
"$PYTHON" "$EMBED_SCRIPT"

step "[8/8] Verifying Neo4j graph"
"$PYTHON" "$CHECK_SCRIPT"

echo
echo "Pipeline complete. Open http://localhost:7474 to inspect the graph."
