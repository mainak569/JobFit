import { useCallback, useEffect, useState } from "react";

import * as api from "../api/client.js";
import { DEMO_RESUME_ID } from "../lib/demo.js";
import { defaultResumeId, forgetResume, getRememberedResumes } from "../lib/resumeStore.js";

function resolveResumeId(requestedId, checks) {
  if (!requestedId || !checks[requestedId]?.missing) return requestedId;
  const fallback = defaultResumeId();
  return checks[fallback]?.missing ? DEMO_RESUME_ID : fallback;
}

/**
 * The resume a page works with, checked against the server. A remembered
 * resume the server no longer has is dropped from the browser's list and the
 * page falls back to the next one, or the sample. The loaded resume also
 * feeds the preview.
 */
export function useSelectedResume(requestedId) {
  const [checks, setChecks] = useState({}); // id -> { resume } | { missing: true } | { error }
  const [removedName, setRemovedName] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const resumeId = resolveResumeId(requestedId, checks);

  useEffect(() => {
    if (!resumeId) return undefined;
    let cancelled = false;
    api.getResume(resumeId).then(
      (resume) => {
        if (!cancelled) setChecks((current) => ({ ...current, [resumeId]: { resume } }));
      },
      (error) => {
        if (cancelled) return;
        if (error.code === "not_found") {
          const forgotten = getRememberedResumes().find((resume) => resume.id === resumeId);
          forgetResume(resumeId);
          setRemovedName(forgotten?.filename ?? "That resume");
          setChecks((current) => ({ ...current, [resumeId]: { missing: true } }));
        } else {
          setChecks((current) => ({ ...current, [resumeId]: { error } }));
        }
      }
    );
    return () => {
      cancelled = true;
    };
  }, [resumeId, attempt]);

  const retry = useCallback(() => {
    setChecks((current) => {
      const copy = { ...current };
      delete copy[resumeId];
      return copy;
    });
    setAttempt((count) => count + 1);
  }, [resumeId]);

  const check = resumeId ? checks[resumeId] : null;
  let status = "none";
  if (check === undefined) status = "loading";
  else if (check?.resume) status = "ready";
  else if (check?.error) status = "error";
  else if (check?.missing) status = "missing";

  return { resumeId, status, resume: check?.resume ?? null, error: check?.error ?? null, removedName, retry };
}
