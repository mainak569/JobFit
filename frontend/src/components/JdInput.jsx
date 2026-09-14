import { formatNumber } from "../lib/format.js";
import { MAX_JD_CHARACTERS } from "../lib/limits.js";

const PLACEHOLDER = `Paste the whole job post, including the requirements.

For example:
We're hiring a frontend engineer with 1–3 years of React and TypeScript. You'll build dashboards, write tests with Jest, and work with our Django API…`;

export default function JdInput({ value, onChange }) {
  const length = value.text.trim().length;
  const isOverLimit = length > MAX_JD_CHARACTERS;

  function update(field) {
    return (event) => {
      const next = event.target.value;
      onChange((current) => ({ ...current, [field]: next }));
    };
  }

  return (
    <div className="jd-input">
      <div className="field">
        <label className="field__label" htmlFor="jd-text">
          Job description
        </label>
        <textarea
          id="jd-text"
          className="input textarea"
          value={value.text}
          onChange={update("text")}
          placeholder={PLACEHOLDER}
          aria-describedby="jd-count"
          aria-invalid={isOverLimit}
        />
        <p id="jd-count" className={isOverLimit ? "count count--over" : "count"} aria-live="polite">
          {formatNumber(length)} / {formatNumber(MAX_JD_CHARACTERS)} characters
        </p>
      </div>
      <div className="field-row">
        <div className="field">
          <label className="field__label" htmlFor="jd-title">
            Job title <span className="optional">(optional)</span>
          </label>
          <input
            id="jd-title"
            className="input"
            value={value.title}
            onChange={update("title")}
            maxLength={255}
            autoComplete="off"
          />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="jd-company">
            Company <span className="optional">(optional)</span>
          </label>
          <input
            id="jd-company"
            className="input"
            value={value.company}
            onChange={update("company")}
            maxLength={255}
            autoComplete="off"
          />
        </div>
      </div>
    </div>
  );
}
