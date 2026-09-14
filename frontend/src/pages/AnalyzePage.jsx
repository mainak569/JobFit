import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ErrorState, WakingUpNotice } from "../components/Feedback.jsx";
import JdInput from "../components/JdInput.jsx";
import ResultsPanel from "../components/ResultsPanel.jsx";
import { ResultsSkeleton } from "../components/Skeleton.jsx";
import UploadZone from "../components/UploadZone.jsx";
import { useAnalysis } from "../hooks/useAnalysis.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { formatNumber } from "../lib/format.js";
import { MAX_JD_CHARACTERS, MIN_JD_CHARACTERS } from "../lib/limits.js";

const EMPTY_JD = { text: "", title: "", company: "" };

/** Why the Analyze button is disabled, in words, or null if it isn't. */
function getAnalyzeBlocker(state, jdText) {
  if (state.resumeStatus === "uploading" || state.resumeStatus === "loading") {
    return "Wait for the resume to finish uploading.";
  }
  if (state.resume === null) {
    return "Upload a resume PDF first.";
  }
  if (state.isDemo) {
    return "Upload your own resume to analyze a new job description.";
  }
  const length = jdText.trim().length;
  if (length === 0) {
    return "Paste a job description.";
  }
  if (length < MIN_JD_CHARACTERS) {
    return `Add at least ${MIN_JD_CHARACTERS - length} more characters to the job description.`;
  }
  if (length > MAX_JD_CHARACTERS) {
    return `Shorten the job description by ${formatNumber(length - MAX_JD_CHARACTERS)} characters.`;
  }
  return null;
}

function focusResults() {
  // Wait a frame so the results have rendered before moving focus to them.
  requestAnimationFrame(() => document.getElementById("results-heading")?.focus());
}

export default function AnalyzePage() {
  useDocumentTitle("Analyze");
  const { state, uploadResume, analyze, loadAnalysis, loadDemo, retryUpload, retryAnalysis } = useAnalysis();
  const [jd, setJd] = useState(EMPTY_JD);
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedAnalysisId = searchParams.get("analysis");

  // WHY a ref: the effect below must know which analysis is on screen, but
  // must not re-run when that changes. After a new analysis finishes, state
  // updates one render before the URL does; if the shown id were a dependency,
  // that in-between render would see "URL says old id, screen shows new id"
  // and reload the old analysis over the new one.
  const shownAnalysisIdRef = useRef(null);
  const shownAnalysisId = state.analysis?.id ?? null;

  // Declared before the loading effect so the ref is current when that effect runs.
  useEffect(() => {
    shownAnalysisIdRef.current = shownAnalysisId;
  }, [shownAnalysisId]);

  useEffect(() => {
    if (requestedAnalysisId && requestedAnalysisId !== shownAnalysisIdRef.current) {
      loadAnalysis(requestedAnalysisId);
    }
  }, [requestedAnalysisId, loadAnalysis]);

  const blocker = getAnalyzeBlocker(state, jd.text);
  const isAnalyzing = state.analysisStatus === "loading";

  async function handleSubmit(event) {
    event.preventDefault();
    if (blocker !== null || isAnalyzing) return;
    const created = await analyze(state.resume.id, {
      jdText: jd.text.trim(),
      title: jd.title.trim(),
      company: jd.company.trim(),
    });
    if (created) {
      // Put the id in the URL so a refresh or a shared link shows the same result.
      setSearchParams({ analysis: created.id });
      focusResults();
    }
  }

  function handleFile(file) {
    // Drop ?analysis= too, or a refresh would bring back the old result.
    setSearchParams({});
    uploadResume(file);
  }

  async function handleTryDemo() {
    const loaded = await loadDemo();
    if (loaded) {
      setSearchParams({ analysis: loaded.id });
      focusResults();
    }
  }

  return (
    <div className="analyze">
      <section className="intro">
        <h1>Check your resume against a job description</h1>
        <p className="lede">
          Upload a resume and paste a job post. You'll see which skills match, which are missing, and what to change.
        </p>
        <div className="intro__actions">
          {/*
            WHY a demo button: most visitors, recruiters especially, will not
            upload a personal document to a site they found five seconds ago.
            One click on precomputed sample data shows what the tool does with
            nothing of theirs uploaded.
          */}
          <button type="button" className="button button--secondary" onClick={handleTryDemo} disabled={isAnalyzing}>
            Try the demo
          </button>
          <p className="hint">Uses a sample resume, so nothing of yours is uploaded.</p>
        </div>
      </section>

      {state.wakingUp && <WakingUpNotice />}

      <form className="inputs" onSubmit={handleSubmit} noValidate>
        <UploadZone
          status={state.resumeStatus}
          progress={state.uploadProgress}
          resume={state.resume}
          isDemo={state.isDemo}
          error={state.resumeError}
          onFile={handleFile}
          onRetry={retryUpload}
        />
        <JdInput value={jd} onChange={setJd} />
        <div className="inputs__actions">
          <button
            type="submit"
            className="button button--primary"
            disabled={blocker !== null || isAnalyzing}
            aria-describedby={blocker ? "analyze-blocker" : undefined}
          >
            {isAnalyzing ? "Analyzing…" : "Analyze match"}
          </button>
          {blocker && (
            <p id="analyze-blocker" className="hint">
              {blocker}
            </p>
          )}
        </div>
      </form>

      <div className="results-area">
        {state.analysisStatus === "loading" && <ResultsSkeleton />}
        {state.analysisStatus === "error" && (
          <ErrorState title="Couldn't show the analysis" error={state.analysisError} onRetry={retryAnalysis} />
        )}
        {state.analysisStatus === "ready" && state.analysis && (
          // key: a different analysis starts fresh (gauge from 0, no skill selected).
          <ResultsPanel
            key={state.analysis.id}
            analysis={state.analysis}
            resumeText={state.resume?.extractedText ?? ""}
          />
        )}
      </div>
    </div>
  );
}
