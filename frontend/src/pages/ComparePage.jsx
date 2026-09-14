import { Link, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorState, WakingUpNotice } from "../components/Feedback.jsx";
import ResumePicker from "../components/ResumePicker.jsx";
import { TableSkeleton } from "../components/Skeleton.jsx";
import { useCompare } from "../hooks/useCompare.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { CATEGORY_LABELS } from "../lib/format.js";
import { defaultResumeId } from "../lib/resumeStore.js";

const CELL_TEXT = {
  present: { symbol: "✓", label: "In the resume" },
  absent: { symbol: "✕", label: "Missing from the resume" },
  none: { symbol: "–", label: "Not asked for" },
};

function CellMark({ value }) {
  const kind = value ?? "none";
  const text = CELL_TEXT[kind];
  return (
    <span className={`mark mark--${kind}`}>
      <span aria-hidden="true">{text.symbol}</span>
      <span className="sr-only">{text.label}</span>
    </span>
  );
}

function CompareTable({ data }) {
  if (data.columns.length === 0) {
    return (
      <EmptyState title="Nothing to compare yet">
        <p>Check this resume against at least one job description first.</p>
        <Link to="/" className="button button--primary">
          Analyze a job description
        </Link>
      </EmptyState>
    );
  }

  return (
    <>
      <ul className="legend">
        {Object.keys(CELL_TEXT).map((kind) => (
          <li key={kind}>
            <span className={`mark mark--${kind}`} aria-hidden="true">
              {CELL_TEXT[kind].symbol}
            </span>
            {CELL_TEXT[kind].label}
          </li>
        ))}
      </ul>

      {/* tabIndex lets keyboard users scroll the table sideways on small screens. */}
      <div className="compare-scroll" role="region" aria-label="Skills compared across job descriptions" tabIndex={0}>
        <table className="compare-table">
          <thead>
            <tr>
              <th scope="col" className="sticky-col">
                Skill
              </th>
              {data.columns.map((column) => (
                <th scope="col" key={column.analysis_id} className="compare-table__job">
                  <Link to={`/?analysis=${column.analysis_id}`} className="table-link">
                    {column.title || "Untitled job"}
                  </Link>
                  {column.company && <span className="compare-table__company">{column.company}</span>}
                  <span className="compare-table__score">Score {column.overall_score}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.name}>
                <th scope="row" className="sticky-col">
                  {row.name}
                  <span className="compare-table__category">{CATEGORY_LABELS[row.category] ?? row.category}</span>
                </th>
                {row.cells.map((cell, index) => (
                  <td key={data.columns[index].analysis_id}>
                    <CellMark value={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function ComparePage() {
  useDocumentTitle("Compare");
  const [searchParams, setSearchParams] = useSearchParams();
  const resumeId = searchParams.get("resume") || defaultResumeId();
  const compare = useCompare(resumeId);

  return (
    <div className="page-stack">
      <header className="page-header">
        <h1>Compare job descriptions</h1>
        <p className="lede">Skills each job asks for, and which of them this resume already has.</p>
      </header>

      <div className="toolbar">
        <ResumePicker value={resumeId} onChange={(id) => setSearchParams({ resume: id })} />
      </div>

      {compare.wakingUp && <WakingUpNotice />}
      {compare.status === "loading" && <TableSkeleton rows={8} />}
      {compare.status === "error" && (
        <ErrorState title="Couldn't load the comparison" error={compare.error} onRetry={compare.retry} />
      )}
      {compare.status === "ready" && <CompareTable data={compare.data} />}
    </div>
  );
}
