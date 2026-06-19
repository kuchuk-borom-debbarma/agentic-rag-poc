import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, BarChart3, ChevronLeft, ChevronRight, Database, GitBranch, Loader2, MessageSquare, Network, Send } from "lucide-react";
import { askQuestion, ingestDocument, loadAnalytics, loadGraph } from "./api";
import EvaluationView from "./evaluation/EvaluationView";
import TracePanel from "./TracePanel";
import "./styles.css";

function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [graph, setGraph] = useState(null);
  const [graphOffset, setGraphOffset] = useState(0);
  const [graphLimit, setGraphLimit] = useState(5000);
  const [stageRun, setStageRun] = useState(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (activeTab === "analytics") {
      refreshAnalytics();
    }
    if (activeTab === "graph") {
      refreshGraph(graphOffset, graphLimit);
    }
  }, [activeTab]);

  async function runIngest() {
    setLoading(true);
    setStatus("");
    setStageRun({ type: "ingest", state: "running" });
    try {
      const result = await ingestDocument();
      setStageRun({ type: "ingest", state: "complete", result });
      setStatus(`Ingested ${result.section_count} sections, ${result.chunk_count} chunks, and ${result.graph_chunk_count} graph nodes.`);
      await refreshGraph(0, graphLimit);
    } catch (error) {
      setStageRun({ type: "ingest", state: "error", error: error.message });
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitQuestion(event) {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }
    setLoading(true);
    setStatus("");
    setStageRun({ type: "query", state: "running", query: question.trim() });
    try {
      const result = await askQuestion(question.trim());
      setAnswer(result);
      setStageRun({ type: "query", state: "complete", result });
    } catch (error) {
      setStageRun({ type: "query", state: "error", error: error.message });
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshAnalytics() {
    try {
      setAnalytics(await loadAnalytics());
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function refreshGraph(offset = graphOffset, limit = graphLimit) {
    try {
      const nextGraph = await loadGraph(offset, limit);
      setGraph(nextGraph);
      setGraphOffset(nextGraph.offset);
      setGraphLimit(nextGraph.limit);
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function changeGraphPage(nextOffset) {
    await refreshGraph(Math.max(0, nextOffset), graphLimit);
  }

  async function changeGraphLimit(event) {
    const nextLimit = Number(event.target.value);
    setGraphLimit(nextLimit);
    await refreshGraph(0, nextLimit);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>AWS Agreement RAG</h1>
          <p>FastAPI + React document Q&A</p>
        </div>
        <button className="iconButton" onClick={runIngest} disabled={loading} title="Ingest document">
          {loading ? <Loader2 className="spin" size={18} /> : <Database size={18} />}
          <span>Ingest</span>
        </button>
      </header>

      <nav className="tabs" aria-label="Views">
        <button className={activeTab === "chat" ? "active" : ""} onClick={() => setActiveTab("chat")}>
          <MessageSquare size={18} />
          Chat
        </button>
        <button className={activeTab === "analytics" ? "active" : ""} onClick={() => setActiveTab("analytics")}>
          <BarChart3 size={18} />
          Analytics
        </button>
        <button className={activeTab === "evaluation" ? "active" : ""} onClick={() => setActiveTab("evaluation")}>
          <Activity size={18} />
          Evaluation
        </button>
        <button className={activeTab === "graph" ? "active" : ""} onClick={() => setActiveTab("graph")}>
          <Network size={18} />
          Graph
        </button>
      </nav>

      {status && <div className="notice">{status}</div>}

      {stageRun?.type === "ingest" && (
        <section className="panel stageDock">
          <StageTimeline run={stageRun} stages={INGESTION_STAGES} />
        </section>
      )}

      {activeTab === "chat" ? (
        <section className="panel">
          <StageTimeline run={stageRun?.type === "query" ? stageRun : null} stages={QUERY_STAGES} />
          <form className="questionForm" onSubmit={submitQuestion}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about the AWS Customer Agreement"
            />
            <button className="iconButton primary" disabled={loading || !question.trim()} title="Ask">
              {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              <span>Ask</span>
            </button>
          </form>

          {answer && (
            <div className="answerGrid">
              <article className="answerBox">
                <div className="meta">
                  <span>{answer.answer_found ? "Answer found" : "No answer found"}</span>
                  <span>{answer.latency_ms} ms</span>
                </div>
                <p>{answer.answer}</p>
              </article>
              <section className="sources">
                <h2>Sources</h2>
                {answer.sources.map((source) => (
                  <article className="source" key={source.chunk_id}>
                    <div className="meta">
                      <span>Page {source.page_start}</span>
                      <span>{source.chunk_id}</span>
                    </div>
                    <p>{source.text}</p>
                  </article>
                ))}
              </section>
              <TracePanel trace={answer.trace} />
            </div>
          )}
        </section>
      ) : activeTab === "analytics" ? (
        <AnalyticsView analytics={analytics} onRefresh={refreshAnalytics} />
      ) : activeTab === "graph" ? (
        <GraphView
          graph={graph}
          offset={graphOffset}
          limit={graphLimit}
          onRefresh={() => refreshGraph(graphOffset, graphLimit)}
          onPage={changeGraphPage}
          onLimitChange={changeGraphLimit}
        />
      ) : (
        <EvaluationView />
      )}
    </main>
  );
}

const INGESTION_STAGES = [
  {
    title: "Parse Document Layout",
    detail: "Read the PDF, identify section headings, body blocks, and legal cross-references.",
    visual: "doc",
  },
  {
    title: "Build Section Relationships",
    detail: "Connect parent sections, child sections, and inline references so legal context stays attached.",
    visual: "tree",
  },
  {
    title: "Create Semantic Chunks",
    detail: "Split section text into answer-sized chunks while keeping section lineage and references.",
    visual: "chunks",
  },
  {
    title: "Persist Search Graph",
    detail: "Save hierarchy, chunk sequence, references, and embeddings into SQLite and Chroma.",
    visual: "store",
  },
];

const QUERY_STAGES = [
  {
    title: "Plan Retrieval",
    detail: "Turn the user question into focused sub-queries and target sections.",
    visual: "doc",
  },
  {
    title: "Search Evidence",
    detail: "Embed each sub-query, retrieve semantic matches, and collect exact section evidence.",
    visual: "chunks",
  },
  {
    title: "Verify Context",
    detail: "Ask the verifier whether evidence is enough; expand to parents, children, neighbors, or references when needed.",
    visual: "tree",
  },
  {
    title: "Answer With Sources",
    detail: "Generate the final answer using only retrieved evidence, then log latency and source snippets.",
    visual: "store",
  },
];

function StageTimeline({ run, stages }) {
  if (!run) {
    return null;
  }
  const running = run.state === "running";
  const errored = run.state === "error";

  return (
    <section className={`stageTimeline ${run.state}`}>
      {stages.map((stage, index) => {
        const state = errored && index === 0 ? "bad" : running && index === 0 ? "active" : running ? "pending" : "done";
        return (
          <article className={`stageStep ${state}`} key={stage.title}>
            <StageVisual type={stage.visual} active={state === "active"} />
            <div>
              <span>Step {index + 1}</span>
              <h2>{stage.title}</h2>
              <p>{stage.detail}</p>
            </div>
          </article>
        );
      })}
      {run.state === "complete" && run.result?.sources && (
        <div className="stageSummary">Collected {run.result.sources.length} source snippets in {run.result.latency_ms} ms.</div>
      )}
      {run.state === "complete" && run.result?.section_count && (
        <div className="stageSummary">Stored {run.result.section_count} sections, {run.result.chunk_count} chunks, {run.result.vector_count} vectors.</div>
      )}
      {run.state === "error" && <div className="stageSummary errorText">{run.error}</div>}
    </section>
  );
}

function StageVisual({ type, active }) {
  const className = `stageVisual ${active ? "pulse" : ""}`;
  if (type === "tree") {
    return (
      <div className={className}>
        <GitBranch size={28} />
        <span />
      </div>
    );
  }
  if (type === "chunks") {
    return (
      <div className={className}>
        <div className="miniChunks"><i /><i /><i /></div>
      </div>
    );
  }
  if (type === "store") {
    return (
      <div className={className}>
        <Database size={28} />
      </div>
    );
  }
  return (
    <div className={className}>
      <MessageSquare size={28} />
    </div>
  );
}

function GraphView({ graph, offset, limit, onRefresh, onPage, onLimitChange }) {
  const totalNodes = graph?.total_nodes || 0;
  const nextOffset = offset + limit;
  const hasNext = nextOffset < totalNodes;

  return (
    <section className="panel graphPanel">
      <div className="graphToolbar">
        <div className="metrics graphMetrics">
          <Metric label="Sections" value={graph?.sections_count || 0} />
          <Metric label="Chunks" value={graph?.chunks_count || 0} />
          <Metric label="References" value={graph?.references_count || 0} />
        </div>
        <div className="graphControls">
          <button className="iconButton" type="button" onClick={onRefresh} title="Refresh graph">
            <Network size={18} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {graph && (
        <div className="notice warning" style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          Warning: We are showing the full graph only because it's a small PDF. Rendering large graphs may cause performance issues.
        </div>
      )}

      {graph ? (
        <>
          <div className="graphRange">
            Showing all {graph.total_nodes} nodes and {graph.total_edges} edges.
          </div>
          <GraphCanvas graph={graph} />
          <GraphLegend />
        </>
      ) : (
        <div className="emptyState">Run ingestion, then refresh graph.</div>
      )}
    </section>
  );
}

function GraphCanvas({ graph }) {
  const width = 1040;
  const height = 520;
  const sectionNodes = graph.nodes.filter((node) => node.kind === "section");
  const chunkNodes = graph.nodes.filter((node) => node.kind === "chunk");
  const positions = new Map();

  sectionNodes.forEach((node, index) => {
    positions.set(node.id, pointFor(index, sectionNodes.length, 250, 190, width * 0.34, height * 0.5));
  });
  chunkNodes.forEach((node, index) => {
    positions.set(node.id, pointFor(index, chunkNodes.length, 320, 220, width * 0.68, height * 0.5));
  });

  return (
    <div className="graphCanvas" role="img" aria-label="Generated ingestion graph">
      <svg viewBox={`0 0 ${width} ${height}`}>
        {graph.edges.map((edge, index) => {
          const source = positions.get(edge.source);
          const target = positions.get(edge.target);
          if (!source || !target) {
            return null;
          }
          return (
            <line
              key={`${edge.source}-${edge.target}-${edge.kind}-${index}`}
              className={`graphEdge ${edge.kind}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
            />
          );
        })}
        {graph.nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) {
            return null;
          }
          return (
            <g className={`graphNode ${node.kind}`} key={node.id} transform={`translate(${position.x}, ${position.y})`}>
              <circle r={node.kind === "section" ? 16 : 10} />
              <text x={node.kind === "section" ? 22 : 16} y="5">{shortLabel(node.label)}</text>
              <title>{node.text_preview || node.label}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function pointFor(index, total, radiusX, radiusY, centerX, centerY) {
  if (total <= 1) {
    return { x: centerX, y: centerY };
  }
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  return {
    x: centerX + Math.cos(angle) * radiusX,
    y: centerY + Math.sin(angle) * radiusY,
  };
}

function shortLabel(value) {
  return value.length > 34 ? `${value.slice(0, 31)}...` : value;
}

function GraphLegend() {
  return (
    <div className="graphLegend">
      <span><i className="sectionDot" /> Section</span>
      <span><i className="chunkDot" /> Chunk</span>
      <span><i className="containsLine" /> Contains</span>
      <span><i className="referenceLine" /> References</span>
      <span><i className="sequenceLine" /> Next chunk</span>
    </div>
  );
}

function AnalyticsView({ analytics, onRefresh }) {
  if (!analytics) {
    return (
      <section className="panel">
        <button className="iconButton" onClick={onRefresh} title="Refresh analytics">
          <BarChart3 size={18} />
          <span>Refresh</span>
        </button>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="metrics">
        <Metric label="Queries" value={analytics.total_queries} />
        <Metric label="Answer rate" value={`${Math.round(analytics.answer_found_rate * 100)}%`} />
        <Metric label="Avg latency" value={`${Math.round(analytics.average_latency_ms)} ms`} />
      </div>

      <div className="tables">
        <Table title="Frequent Questions" rows={analytics.frequent_questions} columns={["query", "count"]} />
        <Table title="No Answer Queries" rows={analytics.no_answer_queries} columns={["query", "created_at"]} />
      </div>
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Table({ title, rows, columns }) {
  return (
    <article className="tableCard">
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{row[column]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

createRoot(document.getElementById("root")).render(<App />);
