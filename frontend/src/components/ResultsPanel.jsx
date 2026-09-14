import { memo, useCallback, useMemo, useState } from "react";

import { jobLabel } from "../lib/format.js";
import ResumeText from "./ResumeText.jsx";
import ScoreGauge from "./ScoreGauge.jsx";
import SkillChipList from "./SkillChips.jsx";

const NO_SPANS = [];

function CategoryBars({ categories }) {
  const entries = Object.entries(categories);
  if (entries.length === 0) {
    return <p className="hint">This job description doesn't name any skills JobFit recognises.</p>;
  }
  return (
    <ul className="bars">
      {entries.map(([key, category]) => (
        <li key={key} className="bars__row">
          <span className="bars__label">{category.label}</span>
          <span className="bars__track" aria-hidden="true">
            <span className="bars__fill" style={{ width: `${Math.round(category.coverage * 100)}%` }} />
          </span>
          <span className="bars__value">
            {category.matched} of {category.required}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ResultsPanel({ analysis, resumeText }) {
  const [selectedSkill, setSelectedSkill] = useState(null);

  // useCallback keeps this function identical between renders, so the
  // memoized chip lists see unchanged props (see SkillChips.jsx).
  const handleSelectSkill = useCallback((name) => {
    setSelectedSkill((current) => (current === name ? null : name));
  }, []);

  const selectedSpans = useMemo(() => {
    const skill = analysis.matched_skills.find((candidate) => candidate.name === selectedSkill);
    return skill?.resume_spans ?? NO_SPANS;
  }, [analysis, selectedSkill]);

  const matched = analysis.matched_skills;
  const missing = analysis.missing_skills;
  const totalSkills = matched.length + missing.length;
  const jobDescription = analysis.job_description;

  return (
    <section className="results" aria-labelledby="results-heading">
      <header className="results__header">
        <h2 id="results-heading" tabIndex={-1}>
          {jobLabel(jobDescription)}
          {jobDescription.company && <span className="results__company"> at {jobDescription.company}</span>}
        </h2>
      </header>

      <div className="results__grid">
        <div className="results__summary">
          <div className="score-row">
            <ScoreGauge score={analysis.overall_score} />
            <dl className="facts">
              <div className="facts__item">
                <dt>Skills covered</dt>
                <dd>
                  {matched.length} of {totalSkills}
                </dd>
              </div>
              <div className="facts__item">
                <dt>Wording overlap</dt>
                <dd>{Math.round(analysis.similarity_score * 100)}%</dd>
              </div>
            </dl>
          </div>

          <div className="section">
            <h3>Coverage by area</h3>
            <CategoryBars categories={analysis.category_scores} />
          </div>

          <div className="section">
            <h3>What to change</h3>
            <ul className="suggestions">
              {analysis.suggestions.map((suggestion) => (
                <li key={suggestion}>{suggestion}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="results__detail">
          <div className="section">
            <div className="section__heading">
              <h3>Skills in both</h3>
              {matched.length > 0 && <p className="hint">Select a skill to find it in the resume.</p>}
            </div>
            <SkillChipList
              kind="matched"
              skills={matched}
              selectedName={selectedSkill}
              onSelect={handleSelectSkill}
            />
          </div>

          <div className="section">
            <div className="section__heading">
              <h3>Missing from the resume</h3>
              {missing.length > 0 && <p className="hint">Most-mentioned first.</p>}
            </div>
            <SkillChipList kind="missing" skills={missing} />
          </div>

          <div className="section">
            <h3>Resume text</h3>
            <ResumeText text={resumeText} spans={selectedSpans} skillName={selectedSkill} />
          </div>
        </div>
      </div>
    </section>
  );
}

// WHY memo here too: the Analyze page re-renders on every keystroke in the job
// description box while results are on screen. The results only depend on the
// analysis and the resume text, so there is no reason to re-render the whole
// panel (gauge, bars, chips, a few thousand characters of resume) per key.
export default memo(ResultsPanel);
