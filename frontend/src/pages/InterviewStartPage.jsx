import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ErrorState, WakingUpNotice } from "../components/Feedback.jsx";
import ResumePicker from "../components/ResumePicker.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { useStartInterview } from "../hooks/useInterview.js";
import { formatDate, formatNumber, jobLabel } from "../lib/format.js";
import { INTERVIEW_ROLES } from "../lib/interviewRoles.js";
import { getRememberedInterviews } from "../lib/interviewStore.js";
import { MAX_JD_CHARACTERS, MIN_JD_CHARACTERS } from "../lib/limits.js";
import { getRememberedResumes } from "../lib/resumeStore.js";

function getStartBlocker({ target, resumeId, jdText }) {
  if (target === "resume" && !resumeId) {
    return "Choose a resume, or interview for a role instead.";
  }
  if (target === "jd") {
    const length = jdText.trim().length;
    if (length === 0) return "Paste a job description.";
    if (length < MIN_JD_CHARACTERS) {
      return `Add at least ${MIN_JD_CHARACTERS - length} more characters to the job description.`;
    }
    if (length > MAX_JD_CHARACTERS) {
      return `Shorten the job description by ${formatNumber(length - MAX_JD_CHARACTERS)} characters.`;
    }
  }
  return null;
}

function PrivacyNote() {
  return (
    <p className="hint">
      Your resume text (without email or phone number) and your answers are sent to Google Gemini or Groq to run
      the interview.
    </p>
  );
}

function FromAnalysis({ state, starting, onStart, onSetUpOther }) {
  if (state.analysisStatus === "loading") {
    return (
      <p className="hint" role="status">
        Loading the analysis…
      </p>
    );
  }
  if (state.analysisStatus === "error") {
    return (
      <div className="section">
        <ErrorState title="Couldn't load the analysis" error={state.analysisError} />
        <button type="button" className="link-button" onClick={onSetUpOther}>
          Set up an interview without it
        </button>
      </div>
    );
  }
  if (!state.analysis) return null;

  const { job_description: job, overall_score: score, matched_skills: matched, missing_skills: missing } =
    state.analysis;
  return (
    <section className="interview-card" aria-labelledby="from-analysis-heading">
      <p className="interview-card__eyebrow">From your analysis</p>
      <h2 id="from-analysis-heading">
        {jobLabel(job)}
        {job.company && <span className="results__company"> at {job.company}</span>}
      </h2>
      <p className="hint">
        Match score {score}. Questions are picked from its {matched.length} matched skills and {missing.length} gaps.
      </p>
      <div className="inputs__actions">
        <button type="button" className="button button--primary" onClick={onStart} disabled={starting}>
          {starting ? "Preparing questions…" : "Start interview"}
        </button>
        <button type="button" className="link-button" onClick={onSetUpOther}>
          Set up a different interview
        </button>
      </div>
    </section>
  );
}

function RecentInterviews({ interviews }) {
  if (interviews.length === 0) return null;
  return (
    <section className="section" aria-labelledby="recent-heading">
      <h2 id="recent-heading">Your interviews</h2>
      <ul className="recent-list">
        {interviews.map((interview) => (
          <li key={interview.id} className="recent-list__item">
            <Link to={`/interview/${interview.id}`}>{interview.title || "Mock interview"}</Link>
            <span className="hint">
              {formatDate(interview.createdAt)} ·{" "}
              {interview.status === "completed"
                ? interview.score === null
                  ? "Finished"
                  : `Scored ${interview.score}`
                : "In progress"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function InterviewStartPage() {
  useDocumentTitle("Interview");
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const analysisId = searchParams.get("analysis");
  const { state, loadAnalysis, clearAnalysis, start } = useStartInterview();

  const [resumeId, setResumeId] = useState(() => getRememberedResumes()[0]?.id ?? "");
  const [target, setTarget] = useState("role");
  const [role, setRole] = useState(INTERVIEW_ROLES[0].key);
  const [jdText, setJdText] = useState("");
  const recent = useMemo(() => getRememberedInterviews(), []);
  const lastPayloadRef = useRef(null);

  useEffect(() => {
    if (analysisId) {
      loadAnalysis(analysisId);
    } else {
      clearAnalysis();
    }
  }, [analysisId, loadAnalysis, clearAnalysis]);

  const starting = state.status === "starting";
  const blocker = getStartBlocker({ target, resumeId, jdText });

  async function startWith(payload) {
    lastPayloadRef.current = payload;
    const session = await start(payload);
    if (session) {
      navigate(`/interview/${session.id}`);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (blocker !== null || starting) return;
    startWith({
      resumeId: resumeId || undefined,
      role: target === "role" ? role : undefined,
      jdText: target === "jd" ? jdText.trim() : undefined,
    });
  }

  const jdLength = jdText.trim().length;

  return (
    <div className="page-stack interview-start">
      <header className="page-header">
        <h1>Practice a mock interview</h1>
        <p className="lede">
          An AI interviewer asks about six questions based on your resume and the job, follows up when an answer is
          thin, and grades every answer at the end.
        </p>
      </header>

      {state.wakingUp && <WakingUpNotice />}

      {analysisId ? (
        <FromAnalysis
          state={state}
          starting={starting}
          onStart={() => startWith({ analysisId })}
          onSetUpOther={() => setSearchParams({})}
        />
      ) : (
        <form className="interview-setup" onSubmit={handleSubmit} noValidate>
          <ResumePicker value={resumeId} onChange={setResumeId} noneLabel="No resume" />

          <fieldset className="choice-group">
            <legend className="field__label">Interview for</legend>
            <label className="choice">
              <input type="radio" name="target" value="role" checked={target === "role"} onChange={() => setTarget("role")} />
              A role
            </label>
            <label className="choice">
              <input type="radio" name="target" value="jd" checked={target === "jd"} onChange={() => setTarget("jd")} />
              A job description I paste
            </label>
            <label className="choice">
              <input
                type="radio"
                name="target"
                value="resume"
                checked={target === "resume"}
                onChange={() => setTarget("resume")}
              />
              Just my resume
            </label>
          </fieldset>

          {target === "role" && (
            <fieldset className="choice-group">
              <legend className="field__label">Role</legend>
              <div className="role-options">
                {INTERVIEW_ROLES.map((option) => (
                  <label key={option.key} className="role-option">
                    <input
                      type="radio"
                      name="role"
                      value={option.key}
                      checked={role === option.key}
                      onChange={() => setRole(option.key)}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {target === "jd" && (
            <div className="field">
              <label className="field__label" htmlFor="interview-jd">
                Job description
              </label>
              <textarea
                id="interview-jd"
                className="input textarea"
                value={jdText}
                onChange={(event) => setJdText(event.target.value)}
                placeholder="Paste the whole job post, including the requirements."
                aria-describedby="interview-jd-count"
                aria-invalid={jdLength > MAX_JD_CHARACTERS}
              />
              <p
                id="interview-jd-count"
                className={jdLength > MAX_JD_CHARACTERS ? "count count--over" : "count"}
                aria-live="polite"
              >
                {formatNumber(jdLength)} / {formatNumber(MAX_JD_CHARACTERS)} characters
              </p>
            </div>
          )}

          <div className="inputs__actions">
            <button
              type="submit"
              className="button button--primary"
              disabled={blocker !== null || starting}
              aria-describedby={blocker ? "start-blocker" : undefined}
            >
              {starting ? "Preparing questions…" : "Start interview"}
            </button>
            {blocker && (
              <p id="start-blocker" className="hint">
                {blocker}
              </p>
            )}
          </div>
        </form>
      )}

      <PrivacyNote />

      {state.status === "error" && (
        <ErrorState
          title="Couldn't start the interview"
          error={state.error}
          onRetry={() => lastPayloadRef.current && startWith(lastPayloadRef.current)}
        />
      )}

      <RecentInterviews interviews={recent} />
    </div>
  );
}
