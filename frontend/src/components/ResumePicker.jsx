import { DEMO_RESUME_ID } from "../lib/demo.js";
import { formatDate } from "../lib/format.js";
import { getRememberedResumes } from "../lib/resumeStore.js";

export default function ResumePicker({ value, onChange, noneLabel = null }) {
  // Read on every render: a resume the server no longer has is removed from the list.
  const resumes = getRememberedResumes();

  return (
    <div className="field picker">
      <label className="field__label" htmlFor="resume-picker">
        Resume
      </label>
      <select id="resume-picker" className="input" value={value} onChange={(event) => onChange(event.target.value)}>
        {noneLabel && <option value="">{noneLabel}</option>}
        {resumes.map((resume) => (
          <option key={resume.id} value={resume.id}>
            {resume.filename}, uploaded {formatDate(resume.createdAt)}
          </option>
        ))}
        <option value={DEMO_RESUME_ID}>Sample resume (demo)</option>
      </select>
      <p className="hint">Only resumes uploaded from this browser are listed.</p>
    </div>
  );
}
