const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function ingestDocument() {
  return request("/api/v1/ingest", { method: "POST" });
}

export async function askQuestion(query) {
  return request("/api/v1/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export async function loadAnalytics() {
  return request("/api/v1/analytics");
}

export async function runEvaluation(topK) {
  return request("/api/v1/evaluation/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ top_k: topK || undefined }),
  });
}

export async function loadEvaluationRuns() {
  return request("/api/v1/evaluation/runs");
}

export async function loadEvaluationRun(runId) {
  return request(`/api/v1/evaluation/runs/${runId}`);
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return payload;
}
