import React, { useState } from "react";
import { ChevronDown, ChevronRight, Search } from "lucide-react";

function TracePanel({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace) {
    return null;
  }

  return (
    <article className="tracePanel">
      <button className="traceToggle" type="button" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        <Search size={16} />
        <span>Retrieval Trace</span>
      </button>

      {open && (
        <div className="traceBody">
          {trace.retrieval_steps.map((step) => (
            <section className="traceStep" key={step.query_id}>
              <header>
                <strong>{step.query_id}</strong>
                <span>{step.query}</span>
              </header>
              <p>{step.expanded_query}</p>
              <div className="traceMeta">
                <span>Explicit: {list(step.explicit_sections)}</span>
                <span>Validated: {list(step.validated_sections)}</span>
                <span>Expansion: {list(step.expansion_actions)}</span>
                <span>Verifier: {step.verifier ? (step.verifier.is_sufficient ? "sufficient" : "insufficient") : "not run"}</span>
              </div>
              <CandidateList title="Vector" candidates={step.vector_candidates} />
              <CandidateList title="Lexical" candidates={step.lexical_candidates} />
              <CandidateList title="Reranked" candidates={step.reranked_candidates} />
            </section>
          ))}
        </div>
      )}
    </article>
  );
}

function CandidateList({ title, candidates }) {
  return (
    <div className="traceCandidates">
      <h3>{title}</h3>
      {candidates.length ? (
        candidates.map((candidate) => (
          <div className="traceCandidate" key={`${title}-${candidate.chunk_id}-${candidate.source_type}`}>
            <strong>{candidate.section_number}</strong>
            <span>{candidate.section_title}</span>
            <em>{candidate.source_type}{candidate.score !== null && candidate.score !== undefined ? ` ${candidate.score}` : ""}</em>
            <p>{candidate.text_preview}</p>
          </div>
        ))
      ) : (
        <span className="traceEmpty">None</span>
      )}
    </div>
  );
}

function list(values) {
  return values && values.length ? values.join(", ") : "none";
}

export default TracePanel;
