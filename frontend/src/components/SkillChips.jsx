import { memo } from "react";

/**
 * WHY memo: an analysis can have 40-60 chips, and the Analyze page re-renders
 * often for reasons that have nothing to do with them. Every keystroke in the
 * job description box and every upload progress event (dozens per upload)
 * update page state. Without memo, each of those re-rendered every chip. With
 * memo, a list re-renders only when its own props change: the matched list
 * when the selected skill changes, the missing list essentially never.
 *
 * This only works because the props are stable: `skills` is the same array
 * object from the stored analysis, and `onSelect` is wrapped in useCallback in
 * ResultsPanel. A new array or an inline arrow function would defeat it.
 *
 * The gauge animation never re-rendered the chips to begin with: its
 * per-frame state lives inside ScoreGauge, so only the gauge re-renders.
 */
function SkillChipList({ kind, skills, selectedName = null, onSelect = null }) {
  if (skills.length === 0) {
    return (
      <p className="hint">
        {kind === "matched"
          ? "None of the skills in this job description appear in the resume."
          : "Nothing missing: every skill this job description names is in the resume."}
      </p>
    );
  }

  return (
    <ul className="chips">
      {skills.map((skill) => (
        <li key={skill.name}>
          {kind === "matched" ? (
            <button
              type="button"
              className="chip chip--matched"
              aria-pressed={selectedName === skill.name}
              onClick={() => onSelect(skill.name)}
            >
              {skill.name}
              <span className="chip__count" aria-label={`found ${skill.resume_count} times in the resume`}>
                {skill.resume_count}
              </span>
            </button>
          ) : (
            <span className="chip chip--missing">
              {skill.name}
              {skill.jd_count > 1 && (
                <span className="chip__count" aria-label={`mentioned ${skill.jd_count} times in the job description`}>
                  ×{skill.jd_count}
                </span>
              )}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

export default memo(SkillChipList);
