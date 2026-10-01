import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ErrorState, WakingUpNotice } from "../components/Feedback.jsx";
import InterviewReport from "../components/InterviewReport.jsx";
import VoiceRecorder from "../components/VoiceRecorder.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { useInterview } from "../hooks/useInterview.js";
import { formatNumber } from "../lib/format.js";
import { MAX_ANSWER_CHARACTERS } from "../lib/limits.js";
import { prefersReducedMotion } from "../lib/motion.js";

function Transcript({ messages }) {
  return (
    <ol className="transcript" aria-live="polite">
      {messages.map((message) => (
        <li key={message.order} className={`bubble bubble--${message.speaker}`}>
          <span className="bubble__who">
            {message.speaker === "interviewer" ? "Interviewer" : "You"}
            {message.speaker === "interviewer" && message.is_follow_up && " · follow-up"}
          </span>
          <p className="bubble__text">{message.text}</p>
        </li>
      ))}
    </ol>
  );
}

function progressLabel(session) {
  if (session.status === "completed") return "Finished";
  if (session.questions_done) return "All questions answered";
  return `Question ${session.current_question + 1} of ${session.question_count}`;
}

export default function InterviewPage() {
  const { interviewId } = useParams();
  const { state, reload, sendAnswer, finish, transcribe } = useInterview(interviewId);
  const { session, pending } = state;
  const [answer, setAnswer] = useState("");
  const [recorderStatus, setRecorderStatus] = useState("idle");
  const endRef = useRef(null);
  useDocumentTitle(session?.title ? `Interview: ${session.title}` : "Interview");

  const messageCount = session?.messages.length ?? 0;
  const inProgress = session?.status === "in_progress";

  useEffect(() => {
    if (inProgress) {
      endRef.current?.scrollIntoView({ block: "nearest", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    }
  }, [messageCount, pending, inProgress]);

  const appendSpoken = useCallback((text) => {
    setAnswer((current) => (current.trim() ? `${current.trimEnd()} ${text}` : text));
  }, []);

  if (state.status === "loading") {
    return (
      <div className="page-stack">
        {state.wakingUp && <WakingUpNotice />}
        <p className="hint" role="status">
          Loading the interview…
        </p>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="page-stack">
        <ErrorState title="Couldn't load the interview" error={state.error} onRetry={reload} />
        <Link to="/interview">Start a new interview</Link>
      </div>
    );
  }

  const trimmed = answer.trim();
  const isOverLimit = trimmed.length > MAX_ANSWER_CHARACTERS;
  const canSend =
    inProgress &&
    !session.questions_done &&
    pending === null &&
    recorderStatus === "idle" &&
    trimmed.length > 0 &&
    !isOverLimit;

  async function handleSend(event) {
    event.preventDefault();
    if (!canSend) return;
    if (await sendAnswer(trimmed)) {
      setAnswer("");
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      handleSend(event);
    }
  }

  return (
    <div className="page-stack interview">
      <header className="interview__header">
        <div className="page-header">
          <h1>{session.title || "Mock interview"}</h1>
          <p className="hint">{progressLabel(session)}</p>
        </div>
        {inProgress && !session.questions_done && (
          <button type="button" className="button button--secondary" onClick={finish} disabled={pending !== null}>
            End and get feedback
          </button>
        )}
      </header>

      {session.status === "completed" ? (
        <>
          <InterviewReport session={session} />
          <details className="transcript-details">
            <summary>Transcript</summary>
            <Transcript messages={session.messages} />
          </details>
          <Link to="/interview">Start another interview</Link>
        </>
      ) : (
        <>
          <Transcript messages={session.messages} />

          {pending !== null && (
            <p className="thinking" role="status">
              <span className="notice__pulse" aria-hidden="true" />
              {pending === "finish" ? "Grading your answers…" : "The interviewer is thinking…"}
              {state.wakingUp && " This is taking longer than usual; if the server was asleep it can take about a minute."}
            </p>
          )}

          {state.actionError && (
            <ErrorState
              title={state.failedAction === "finish" ? "Couldn't grade the interview" : "Couldn't send your answer"}
              error={state.actionError}
              onRetry={state.failedAction === "finish" ? finish : undefined}
            />
          )}

          {session.questions_done && pending === null && !state.actionError && (
            <button type="button" className="button button--primary" onClick={finish}>
              Get my feedback
            </button>
          )}

          {!session.questions_done && (
            <form className="composer" onSubmit={handleSend} noValidate>
              <label className="field__label" htmlFor="answer">
                Your answer
              </label>
              <textarea
                id="answer"
                className="input textarea composer__input"
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your answer, or record it."
                aria-describedby="answer-count answer-hint"
                aria-invalid={isOverLimit}
                readOnly={pending !== null}
              />
              <div className="composer__bar">
                <VoiceRecorder
                  transcribe={transcribe}
                  onText={appendSpoken}
                  onStatusChange={setRecorderStatus}
                  disabled={pending !== null}
                />
                <p id="answer-count" className={isOverLimit ? "count count--over" : "count"}>
                  {formatNumber(trimmed.length)} / {formatNumber(MAX_ANSWER_CHARACTERS)}
                </p>
                <button type="submit" className="button button--primary" disabled={!canSend}>
                  Send
                </button>
              </div>
              <p id="answer-hint" className="hint">
                Ctrl + Enter to send. Answer as you would out loud: what you did, how, and why.
              </p>
            </form>
          )}
          <div ref={endRef} />
        </>
      )}
    </div>
  );
}
