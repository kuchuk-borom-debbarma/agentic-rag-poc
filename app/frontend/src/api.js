const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function ingestDocument(onProgress) {
  return request("/api/v1/ingest", { method: "POST" }, onProgress);
}

export async function askQuestion(query, maxLoops, onProgress) {
  return request("/api/v1/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_loops: maxLoops }),
  }, onProgress);
}

export async function loadAnalytics() {
  return request("/api/v1/analytics");
}

export async function loadGraph(offset = 0, limit = 120) {
  return request(`/api/v1/ingest/graph?offset=${offset}&limit=${limit}`);
}

export async function runEvaluation(topK, onProgress) {
  return request("/api/v1/evaluation/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ top_k: topK || undefined }),
  }, onProgress);
}

export async function loadEvaluationRuns() {
  return request("/api/v1/evaluation/runs");
}

export async function loadEvaluationRun(runId) {
  return request(`/api/v1/evaluation/runs/${runId}`);
}

async function request(path, options = {}, onProgress = null) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }

  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("text/event-stream")) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        if (part.startsWith("data: ")) {
          const dataStr = part.slice(6);
          if (dataStr === "[DONE]") continue;
          
          try {
            const data = JSON.parse(dataStr);
            if (data.type === "complete") {
              return data.result;
            }
            if (onProgress && data.type === "progress") {
              onProgress(data);
            }
          } catch (e) {
            console.error("Failed to parse SSE JSON", e, dataStr);
          }
        }
      }
    }
    throw new Error("Stream closed without complete result");
  } else {
    return response.json();
  }
}
