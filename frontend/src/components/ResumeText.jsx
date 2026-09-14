import { Fragment, useEffect, useMemo, useRef } from "react";

import { prefersReducedMotion } from "../lib/motion.js";

/**
 * Split the text into plain and highlighted segments using the spans the
 * backend matcher found.
 *
 * WHY Array.from: the backend's offsets are Python string indices, which count
 * Unicode code points. JavaScript string indices count UTF-16 code units, so a
 * single emoji or other character outside the Basic Multilingual Plane counts
 * as 2 in JS and 1 in Python, and every highlight after it would land one
 * character late. Array.from splits by code point, which matches Python.
 */
function buildSegments(text, spans) {
  const characters = Array.from(text);
  const ordered = [...spans].sort((first, second) => first[0] - second[0]);
  const segments = [];
  let cursor = 0;

  for (const [start, end] of ordered) {
    if (start < cursor) continue; // overlapping span; the earlier one already covers it
    if (start > cursor) {
      segments.push({ text: characters.slice(cursor, start).join(""), highlighted: false });
    }
    segments.push({ text: characters.slice(start, end).join(""), highlighted: true });
    cursor = end;
  }
  if (cursor < characters.length) {
    segments.push({ text: characters.slice(cursor).join(""), highlighted: false });
  }
  return segments;
}

export default function ResumeText({ text, spans, skillName }) {
  const firstMarkRef = useRef(null);
  const segments = useMemo(() => buildSegments(text, spans), [text, spans]);
  // The first highlight gets the ref, so selecting a skill scrolls to it.
  const firstHighlightIndex = segments.findIndex((segment) => segment.highlighted);

  useEffect(() => {
    if (skillName === null || firstMarkRef.current === null) return;
    firstMarkRef.current.scrollIntoView({
      behavior: prefersReducedMotion() ? "auto" : "smooth",
      block: "center",
    });
  }, [skillName]);

  if (!text) {
    return <p className="hint">The resume text isn't available.</p>;
  }

  return (
    <>
      <div className="resume-sheet" tabIndex={0} aria-label="Resume text">
        <p className="resume-sheet__text">
          {segments.map((segment, index) => {
            if (!segment.highlighted) {
              return <Fragment key={index}>{segment.text}</Fragment>;
            }
            return (
              <mark key={index} ref={index === firstHighlightIndex ? firstMarkRef : null}>
                {segment.text}
              </mark>
            );
          })}
        </p>
      </div>
      <p className="sr-only" aria-live="polite">
        {skillName ? `${spans.length} highlighted in the resume for ${skillName}` : ""}
      </p>
    </>
  );
}
