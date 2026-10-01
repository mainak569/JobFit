import { useState } from "react";

import { DEMO_RESUME_ID } from "../lib/demo.js";
import ResumeText from "./ResumeText.jsx";

const NO_SPANS = [];

export function RemovedResumeNotice({ name }) {
  if (!name) return null;
  return (
    <p className="hint" role="status">
      "{name}" isn't on the server any more, so it was removed from this list.
    </p>
  );
}

export default function ResumePreview({ resume }) {
  const [open, setOpen] = useState(false);
  if (!resume) return null;

  const isSample = resume.id === DEMO_RESUME_ID;
  const panelId = `resume-preview-${resume.id}`;

  return (
    <div className="resume-preview">
      <button
        type="button"
        className="button button--secondary button--small"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        {open ? "Hide resume" : isSample ? "Preview the sample resume" : "Preview resume"}
      </button>
      {open && (
        <div id={panelId} className="resume-preview__panel">
          {isSample && (
            <p className="hint">The demo's resume, with contact details removed.</p>
          )}
          <ResumeText text={resume.extracted_text} spans={NO_SPANS} skillName={null} />
        </div>
      )}
    </div>
  );
}
