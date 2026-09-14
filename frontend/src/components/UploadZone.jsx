import { useRef, useState } from "react";

import { isRetryable } from "../api/client.js";
import { formatNumber } from "../lib/format.js";
import { validateResumeFile } from "../lib/validation.js";

function DocumentIcon() {
  return (
    <svg className="upload-zone__icon" width="32" height="40" viewBox="0 0 32 40" aria-hidden="true">
      <path d="M2 2h19l9 9v27H2z" fill="var(--sheet)" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      <path d="M21 2v9h9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      <path d="M8 20h16M8 26h16M8 32h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function UploadProgress({ status, progress }) {
  if (status === "loading") {
    return <p className="upload-zone__title">Loading the resume…</p>;
  }
  const percent = Math.round(progress * 100);
  const allBytesSent = progress >= 1;
  return (
    <div className="upload-progress">
      <p className="upload-zone__title">{allBytesSent ? "Reading the text in your PDF…" : "Uploading…"}</p>
      <div
        className="progress"
        role="progressbar"
        aria-label="Upload progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <div className="progress__fill" style={{ width: `${percent}%` }} />
      </div>
      <p className="hint">{percent}%</p>
    </div>
  );
}

export default function UploadZone({ status, progress, resume, isDemo, error, onFile, onRetry }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState(null);

  const isBusy = status === "uploading" || status === "loading";
  const hasResume = status === "ready" && resume !== null;

  function acceptFile(file) {
    if (isBusy) return;
    const problem = validateResumeFile(file);
    setValidationError(problem);
    if (problem === null) {
      onFile(file);
    }
  }

  function openFilePicker() {
    inputRef.current?.click();
  }

  function handleDragOver(event) {
    event.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(event) {
    // dragleave also fires when the pointer moves onto a child element; only
    // count it as leaving when it goes outside the zone entirely.
    if (event.currentTarget.contains(event.relatedTarget)) return;
    setIsDragging(false);
  }

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    acceptFile(event.dataTransfer.files[0]);
  }

  function handleInputChange(event) {
    acceptFile(event.target.files[0]);
    // Reset so choosing the same file again still fires a change event.
    event.target.value = "";
  }

  function handleZoneClick() {
    if (!isBusy && !hasResume) {
      openFilePicker();
    }
  }

  const shownError = validationError ?? (status === "error" ? error?.message : null);
  const canRetry = validationError === null && status === "error" && isRetryable(error);

  const classNames = ["upload-zone"];
  if (!isBusy && !hasResume) classNames.push("upload-zone--empty");
  if (isDragging) classNames.push("upload-zone--dragging");
  if (hasResume) classNames.push("upload-zone--filled");

  return (
    <div className="field">
      <span className="field__label" id="resume-label">
        Resume
      </span>
      <div
        className={classNames.join(" ")}
        role="group"
        aria-labelledby="resume-label"
        onClick={handleZoneClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          onChange={handleInputChange}
        />

        {isBusy && <UploadProgress status={status} progress={progress} />}

        {!isBusy && hasResume && (
          <>
            <DocumentIcon />
            <div>
              <p className="upload-zone__title">{isDemo ? "Sample resume" : resume.filename}</p>
              <p className="hint">{formatNumber(Array.from(resume.extractedText).length)} characters of text found</p>
            </div>
            {isDemo && (
              <p className="hint">This sample can't be checked against new job posts. Upload your own resume to do that.</p>
            )}
            <button type="button" className="button button--secondary" onClick={openFilePicker}>
              {isDemo ? "Upload my resume" : "Replace resume"}
            </button>
          </>
        )}

        {!isBusy && !hasResume && (
          <>
            <DocumentIcon />
            <p className="upload-zone__title">{isDragging ? "Drop to upload" : "Drop your resume PDF here"}</p>
            {/* No onClick of its own: the click bubbles to the zone, so the picker opens once. */}
            <button type="button" className="button button--secondary">
              Choose a file
            </button>
            <p className="hint">PDF only, up to 5 MB</p>
          </>
        )}
      </div>

      {shownError && (
        <div className="inline-error" role="alert">
          <p>{shownError}</p>
          {canRetry && (
            <button type="button" className="link-button" onClick={onRetry}>
              Try the upload again
            </button>
          )}
        </div>
      )}
    </div>
  );
}
