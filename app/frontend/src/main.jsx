import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, BarChart3, Database, Loader2, MessageSquare, Send } from "lucide-react";
import { askQuestion, ingestDocument, loadAnalytics } from "./api";
import EvaluationView from "./evaluation/EvaluationView";
import "./styles.css";

function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (activeTab === "analytics") {
      refreshAnalytics();
    }
  }, [activeTab]);

  async function runIngest() {
    setLoading(true);
    setStatus("");
    try {
      const result = await ingestDocument();
      setStatus(`Ingested ${result.section_count} sections, ${result.chunk_count} chunks, and ${result.graph_chunk_count} graph nodes.`);
    } catch (error) {
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
    try {
      const result = await askQuestion(question.trim());
      setAnswer(result);
    } catch (error) {
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
      </nav>

      {status && <div className="notice">{status}</div>}

      {activeTab === "chat" ? (
        <section className="panel">
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
            </div>
          )}
        </section>
      ) : activeTab === "analytics" ? (
        <AnalyticsView analytics={analytics} onRefresh={refreshAnalytics} />
      ) : (
        <EvaluationView />
      )}
    </main>
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
