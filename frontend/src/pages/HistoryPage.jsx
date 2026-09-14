import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorState, WakingUpNotice } from "../components/Feedback.jsx";
import ResumePicker from "../components/ResumePicker.jsx";
import { TableSkeleton } from "../components/Skeleton.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { useHistory } from "../hooks/useHistory.js";
import { DEMO_RESUME_ID } from "../lib/demo.js";
import { formatDate, jobLabel } from "../lib/format.js";
import { defaultResumeId } from "../lib/resumeStore.js";

// WHY sort in the browser: the API returns 20 rows per page, newest first.
// Re-sorting the rows already loaded is instant and needs no request. The
// trade-off: with more than 20 analyses, "highest score" only covers the pages
// loaded so far, which is why "Show more" loads the rest.
function sortAnalyses(items, sort) {
  const sorted = [...items];
  sorted.sort((first, second) => {
    let difference;
    if (sort.key === "score") {
      difference = first.overall_score - second.overall_score;
    } else {
      difference = new Date(first.created_at) - new Date(second.created_at);
    }
    return sort.direction === "asc" ? difference : -difference;
  });
  return sorted;
}

function SortableHeader({ label, sortKey, sort, onSort, className }) {
  const isActive = sort.key === sortKey;
  const ariaSort = isActive ? (sort.direction === "asc" ? "ascending" : "descending") : "none";

  function handleClick() {
    if (isActive) {
      onSort({ key: sortKey, direction: sort.direction === "asc" ? "desc" : "asc" });
    } else {
      onSort({ key: sortKey, direction: "desc" });
    }
  }

  return (
    <th scope="col" aria-sort={ariaSort} className={className}>
      <button type="button" className="sort-button" onClick={handleClick}>
        {label}
        <span className={isActive ? "sort-arrow sort-arrow--active" : "sort-arrow"} aria-hidden="true">
          {isActive && sort.direction === "asc" ? "▲" : "▼"}
        </span>
      </button>
    </th>
  );
}

export default function HistoryPage() {
  useDocumentTitle("History");
  const [searchParams, setSearchParams] = useSearchParams();
  const resumeId = searchParams.get("resume") || defaultResumeId();
  const history = useHistory(resumeId);
  const [sort, setSort] = useState({ key: "date", direction: "desc" });
  const [confirmingId, setConfirmingId] = useState(null);
  const isDemo = resumeId === DEMO_RESUME_ID;

  const sortedItems = useMemo(() => sortAnalyses(history.items, sort), [history.items, sort]);

  function confirmDelete(analysisId) {
    setConfirmingId(null);
    history.deleteAnalysis(analysisId);
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <h1>History</h1>
        <p className="lede">Every job description this resume has been checked against.</p>
      </header>

      <div className="toolbar">
        <ResumePicker value={resumeId} onChange={(id) => setSearchParams({ resume: id })} />
      </div>

      {history.wakingUp && <WakingUpNotice />}

      {history.deleteError && (
        <p className="inline-error" role="alert">
          Couldn't delete "{history.deleteError.jobTitle}": {history.deleteError.message} It's back in the list.
        </p>
      )}

      {history.status === "loading" && <TableSkeleton rows={4} />}

      {history.status === "error" && (
        <ErrorState title="Couldn't load the history" error={history.error} onRetry={history.retry} />
      )}

      {history.status === "ready" && sortedItems.length === 0 && (
        <EmptyState title="No analyses yet">
          <p>Check this resume against a job description and it will show up here.</p>
          <Link to="/" className="button button--primary">
            Analyze a job description
          </Link>
        </EmptyState>
      )}

      {history.status === "ready" && sortedItems.length > 0 && (
        <>
          <div className="table-scroll">
            <table className="history-table">
              <caption className="sr-only">Past analyses for the selected resume</caption>
              <thead>
                <tr>
                  <th scope="col">Job</th>
                  <th scope="col" className="col-company">
                    Company
                  </th>
                  <SortableHeader label="Score" sortKey="score" sort={sort} onSort={setSort} className="col-number" />
                  <SortableHeader label="Date" sortKey="date" sort={sort} onSort={setSort} />
                  {!isDemo && (
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {sortedItems.map((item) => {
                  const title = jobLabel(item.job_description);
                  return (
                    <tr key={item.id}>
                      <td>
                        <Link to={`/?analysis=${item.id}`} className="table-link">
                          {title}
                        </Link>
                        {item.job_description.company && (
                          <span className="company-inline">{item.job_description.company}</span>
                        )}
                      </td>
                      <td className="col-company">{item.job_description.company || "–"}</td>
                      <td className="col-number score-cell">{item.overall_score}</td>
                      <td className="date-cell">{formatDate(item.created_at)}</td>
                      {!isDemo && (
                        <td className="actions-cell">
                          {confirmingId === item.id ? (
                            <div className="row-actions">
                              <button
                                type="button"
                                className="button button--danger button--small"
                                onClick={() => confirmDelete(item.id)}
                              >
                                Delete
                              </button>
                              <button
                                type="button"
                                className="button button--secondary button--small"
                                onClick={() => setConfirmingId(null)}
                              >
                                Keep
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="button button--secondary button--small"
                              onClick={() => setConfirmingId(item.id)}
                              aria-label={`Delete the analysis for ${title}`}
                            >
                              Delete
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {history.nextPage !== null && (
            <div className="load-more">
              <button
                type="button"
                className="button button--secondary"
                onClick={history.loadMore}
                disabled={history.loadingMore}
              >
                {history.loadingMore ? "Loading…" : "Show more"}
              </button>
              {history.loadMoreError && <p className="inline-error">{history.loadMoreError.message}</p>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
