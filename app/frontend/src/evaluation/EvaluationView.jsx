import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Target,
  Timer,
  XCircle,
} from "lucide-react";
import { loadEvaluationRun, loadEvaluationRuns, runEvaluation } from "../api";
import TracePanel from "../TracePanel";

const CATEGORY_ICONS = {
  retrieval: Target,
  answer: ShieldCheck,
  system: Timer,
};

function EvaluationView() {
  const [topK, setTopK] = useState("5");
  const [history, setHistory] = useState([]);
  const [detail, setDetail] = useState(null);
  const [expandedCases, setExpandedCases] = useState(new Set());
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refreshHistory();
  }, []);

  async function refreshHistory() {
    setStatus("");
    try {
      const runs = await loadEvaluationRuns();
      setHistory(runs);
      if (!detail && runs.length > 0) {
        setDetail(await loadEvaluationRun(runs[0].run_id));
      }
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function runBenchmark(event) {
    event.preventDefault();
    setLoading(true);
    setStatus("");
    try {
      const parsedTopK = topK ? Number(topK) : undefined;
      const result = await runEvaluation(parsedTopK, (progress) => {
        setStatus(`${progress.message} (${progress.completed}/${progress.total})`);
      });
      setDetail(result);
      setExpandedCases(new Set());
      setHistory(await loadEvaluationRuns());
      setStatus("Evaluation completed successfully.");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function selectRun(runId) {
    setLoading(true);
    setStatus("");
    try {
      setDetail(await loadEvaluationRun(runId));
      setExpandedCases(new Set());
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  function toggleCase(caseId) {
    const next = new Set(expandedCases);
    if (next.has(caseId)) {
      next.delete(caseId);
    } else {
      next.add(caseId);
    }
    setExpandedCases(next);
  }

  return (
    <section className="panel evaluationPanel">
      <form className="evaluationToolbar" onSubmit={runBenchmark}>
        <label className="numberField">
          <span>Top K</span>
          <input
            value={topK}
            onChange={(event) => setTopK(event.target.value)}
            type="number"
            min="1"
            max="20"
          />
        </label>
        <button className="iconButton primary" disabled={loading} title="Run benchmark">
          {loading ? <Loader2 className="spin" size={18} /> : <Activity size={18} />}
          <span>Run all</span>
        </button>
        <button className="iconButton" type="button" onClick={refreshHistory} disabled={loading} title="Refresh history">
          <RefreshCw size={18} />
          <span>Refresh</span>
        </button>
      </form>

      {status && <div className="notice">{status}</div>}

      {detail ? (
        <div className="evaluationResult">
          <RunScoreBand summary={detail.summary} />
          <div className="categoryGrid">
            {detail.categories.map((category) => (
              <CategoryCard category={category} key={category.key} />
            ))}
          </div>
          <RunHistory history={history} activeRunId={detail.summary.run_id} onSelect={selectRun} />
          <CaseResults cases={detail.cases} expandedCases={expandedCases} onToggle={toggleCase} />
        </div>
      ) : (
        <RunHistory history={history} activeRunId="" onSelect={selectRun} />
      )}
    </section>
  );
}

function RunScoreBand({ summary }) {
  return (
    <div className="scoreBand evaluationScoreBand">
      <ScoreCard label="Overall" value={percent(summary.overall_score)} />
      <ScoreCard label="Retrieval" value={percent(summary.retrieval_score)} />
      <ScoreCard label="Answer" value={percent(summary.answer_score)} />
      <ScoreCard label="System" value={percent(summary.system_score)} />
      <ScoreCard label="Pass Rate" value={percent(summary.pass_rate)} />
      <ScoreCard label="Avg Latency" value={`${Math.round(summary.average_latency_ms)} ms`} />
    </div>
  );
}

function ScoreCard({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RunHistory({ history, activeRunId, onSelect }) {
  return (
    <article className="tableCard evaluationHistory">
      <h2>Previous Runs</h2>
      <table>
        <thead>
          <tr>
            <th>Run</th>
            <th>Cases</th>
            <th>Overall</th>
            <th>Retrieval</th>
            <th>Answer</th>
            <th>System</th>
            <th>Avg Latency</th>
          </tr>
        </thead>
        <tbody>
          {history.map((run) => (
            <tr key={run.run_id} className={run.run_id === activeRunId ? "activeRow" : ""}>
              <td>
                <button className="linkButton" type="button" onClick={() => onSelect(run.run_id)}>
                  {formatDate(run.created_at)}
                </button>
              </td>
              <td>{run.case_count}</td>
              <td>{percent(run.overall_score)}</td>
              <td>{percent(run.retrieval_score)}</td>
              <td>{percent(run.answer_score)}</td>
              <td>{percent(run.system_score)}</td>
              <td>{Math.round(run.average_latency_ms)} ms</td>
            </tr>
          ))}
          {history.length === 0 && (
            <tr>
              <td colSpan="7">No benchmark runs yet.</td>
            </tr>
          )}
        </tbody>
      </table>
    </article>
  );
}

function CaseResults({ cases, expandedCases, onToggle }) {
  return (
    <article className="tableCard caseResults">
      <h2>Case Results</h2>
      <div className="caseList">
        {cases.map((caseResult) => {
          const isExpanded = expandedCases.has(caseResult.case.id);
          return (
            <article className={`caseRow ${caseResult.passed ? "passed" : "failed"}`} key={caseResult.case.id}>
              <button className="caseSummary" type="button" onClick={() => onToggle(caseResult.case.id)}>
                {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                <span>{caseResult.case.id}</span>
                <strong>{caseResult.case.query}</strong>
                <ScorePill status={caseResult.passed ? "good" : "bad"} score={caseResult.passed ? 1 : 0} />
              </button>
              <div className="caseMeta">
                <span>Expected: {caseResult.expected_section_numbers.join(", ") || "none"}</span>
                <span>Retrieved: {caseResult.retrieved_section_numbers.join(", ") || "none"}</span>
                <span>{caseResult.latency_ms} ms</span>
              </div>
              {isExpanded && <CaseDetail caseResult={caseResult} />}
            </article>
          );
        })}
      </div>
    </article>
  );
}

function CaseDetail({ caseResult }) {
  const failedMetrics = caseResult.categories.flatMap((category) =>
    category.metrics.filter((metric) => metric.status !== "good")
  );

  return (
    <div className="caseDetail">
      <div className="caseAnswerGrid">
        <article>
          <h3>Expected Answer</h3>
          <p>{caseResult.case.expected_answer}</p>
        </article>
        <article>
          <h3>Actual Answer</h3>
          <p>{caseResult.answer}</p>
        </article>
      </div>

      <div className="categoryGrid compactCategoryGrid">
        {caseResult.categories.map((category) => (
          <CategoryCard category={category} key={category.key} />
        ))}
      </div>

      {failedMetrics.length > 0 && (
        <div className="failedMetricList">
          {failedMetrics.map((metric) => (
            <MetricRow metric={metric} key={`${metric.category}-${metric.key}`} />
          ))}
        </div>
      )}

      <section className="sources evaluationSources">
        <h3>Sources</h3>
        {caseResult.sources.map((source) => (
          <article className="source" key={source.chunk_id}>
            <div className="meta">
              <span>{source.section_number === "front_matter" ? "Front Matter" : `Section ${source.section_number}`}</span>
              <span>{source.source_type}</span>
            </div>
            <p>{source.text}</p>
          </article>
        ))}
      </section>

      <TracePanel trace={caseResult.trace} />
    </div>
  );
}

function CategoryCard({ category }) {
  const Icon = CATEGORY_ICONS[category.key] || Activity;

  return (
    <article className="evaluationCategory">
      <header>
        <div>
          <Icon size={18} />
          <h2>{category.label}</h2>
        </div>
        <ScorePill status={category.status} score={category.score} />
      </header>

      <div className="metricList">
        {category.metrics.map((metric) => (
          <MetricRow metric={metric} key={metric.key} />
        ))}
      </div>
    </article>
  );
}

function MetricRow({ metric }) {
  return (
    <article className={`metricRow ${metric.status}`}>
      <div>
        <div className="metricTitle">
          <StatusIcon status={metric.status} />
          <span>{metric.label}</span>
        </div>
        <p>{metric.details}</p>
      </div>
      <strong>{metric.value}</strong>
    </article>
  );
}

function ScorePill({ status, score }) {
  return <span className={`scorePill ${status}`}>{percent(score)}</span>;
}

function StatusIcon({ status }) {
  if (status === "good") {
    return <CheckCircle2 size={16} />;
  }
  if (status === "warn") {
    return <AlertTriangle size={16} />;
  }
  return <XCircle size={16} />;
}

function percent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function formatDate(value) {
  return new Date(value).toLocaleString();
}

export default EvaluationView;
