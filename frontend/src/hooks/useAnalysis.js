import { useCallback, useReducer, useRef } from "react";

import * as api from "../api/client.js";
import { ApiError } from "../api/client.js";
import { startWakeNotice, withWakeNotice } from "../api/wakeNotice.js";
import { DEMO_RESUME_ID } from "../lib/demo.js";
import { rememberResume } from "../lib/resumeStore.js";

/**
 * Everything the Analyze page does with the API: upload, analyze, load a saved
 * analysis, load the demo. Owns loading, error and cold-start state.
 *
 * WHY components never call fetch themselves: with every request going through
 * hooks like this one, loading/error/"waking up" handling is written once
 * instead of per component, components render purely from props (easy to read
 * and to test with fake data), and changing how we talk to the API touches the
 * api/ and hooks/ folders, not twenty components.
 */

const initialState = {
  resume: null, // { id, filename, extractedText }
  resumeStatus: "idle", // idle | uploading | loading | ready | error
  uploadProgress: 0,
  resumeError: null,
  isDemo: false,
  analysis: null,
  analysisStatus: "idle", // idle | loading | ready | error
  analysisError: null,
  wakingUp: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "resume/uploadStarted":
      // A new resume makes the analysis on screen belong to a different
      // resume, so clear it rather than show results that no longer match.
      return {
        ...state,
        resume: null,
        resumeStatus: "uploading",
        uploadProgress: 0,
        resumeError: null,
        isDemo: false,
        analysis: null,
        analysisStatus: "idle",
        analysisError: null,
      };
    case "resume/uploadProgress":
      return { ...state, uploadProgress: action.progress };
    case "resume/ready":
      return { ...state, resume: action.resume, resumeStatus: "ready", resumeError: null, isDemo: action.isDemo };
    case "resume/failed":
      return { ...state, resumeStatus: "error", resumeError: action.error };
    case "analysis/started":
      return { ...state, analysisStatus: "loading", analysisError: null };
    case "analysis/ready":
      return { ...state, analysis: action.analysis, analysisStatus: "ready" };
    case "analysis/failed":
      return { ...state, analysisStatus: "error", analysisError: action.error };
    case "wakingUp/changed":
      return { ...state, wakingUp: action.wakingUp };
    default:
      throw new Error(`Unknown action: ${action.type}`);
  }
}

function toResume(detail) {
  return { id: detail.id, filename: detail.filename, extractedText: detail.extracted_text };
}

export function useAnalysis() {
  const [state, dispatch] = useReducer(reducer, initialState);
  // The last failed operation, so "Try again" can repeat exactly that.
  const retryUploadRef = useRef(null);
  const retryAnalysisRef = useRef(null);

  const setWakingUp = useCallback((wakingUp) => {
    dispatch({ type: "wakingUp/changed", wakingUp });
  }, []);

  const fetchResume = useCallback(
    async (resumeId) => {
      const detail = await withWakeNotice(api.getResume(resumeId), setWakingUp);
      return toResume(detail);
    },
    [setWakingUp]
  );

  // Named function expressions let each action refer to itself for "Try again"
  // without reading the const before useCallback has returned it.
  const uploadResume = useCallback(
    async function uploadResumeAction(file) {
      retryUploadRef.current = () => uploadResumeAction(file);
      dispatch({ type: "resume/uploadStarted" });

      let stopWakeNotice = null;
      try {
        const created = await api.uploadResume(file, (fraction) => {
          dispatch({ type: "resume/uploadProgress", progress: fraction });
          // WHY start the cold-start timer only once every byte is sent: on a
          // slow connection the upload itself can take longer than 3 seconds,
          // and that isn't the server sleeping. Once the bytes are sent, a long
          // wait for the response is.
          if (fraction >= 1 && stopWakeNotice === null) {
            stopWakeNotice = startWakeNotice(setWakingUp);
          }
        });
        rememberResume({ id: created.id, filename: created.filename, createdAt: created.created_at });

        // The upload response carries only a preview; highlighting needs the full text.
        const resume = await fetchResume(created.id);
        dispatch({ type: "resume/ready", resume, isDemo: false });
        return resume;
      } catch (error) {
        dispatch({ type: "resume/failed", error });
        return null;
      } finally {
        if (stopWakeNotice !== null) {
          stopWakeNotice();
        }
      }
    },
    [fetchResume, setWakingUp]
  );

  const analyze = useCallback(
    async function analyzeAction(resumeId, { jdText, title, company }) {
      retryAnalysisRef.current = () => analyzeAction(resumeId, { jdText, title, company });
      dispatch({ type: "analysis/started" });
      try {
        const created = await withWakeNotice(api.analyze({ resumeId, jdText, title, company }), setWakingUp);
        dispatch({ type: "analysis/ready", analysis: created });
        return created;
      } catch (error) {
        dispatch({ type: "analysis/failed", error });
        return null;
      }
    },
    [setWakingUp]
  );

  const loadAnalysis = useCallback(
    async function loadAnalysisAction(analysisId) {
      retryAnalysisRef.current = () => loadAnalysisAction(analysisId);
      dispatch({ type: "analysis/started" });
      try {
        const loaded = await withWakeNotice(api.getAnalysis(analysisId), setWakingUp);
        const resume = await fetchResume(loaded.resume_id);
        dispatch({ type: "resume/ready", resume, isDemo: loaded.resume_id === DEMO_RESUME_ID });
        dispatch({ type: "analysis/ready", analysis: loaded });
        return loaded;
      } catch (error) {
        const shown =
          error.code === "not_found"
            ? new ApiError({
                code: "not_found",
                message: "That analysis doesn't exist any more. It may have been deleted.",
                status: 404,
              })
            : error;
        dispatch({ type: "analysis/failed", error: shown });
        return null;
      }
    },
    [fetchResume, setWakingUp]
  );

  const loadDemo = useCallback(async function loadDemoAction() {
    retryAnalysisRef.current = () => loadDemoAction();
    dispatch({ type: "analysis/started" });

    let page;
    try {
      page = await withWakeNotice(api.listAnalyses(DEMO_RESUME_ID), setWakingUp);
    } catch (error) {
      dispatch({ type: "analysis/failed", error });
      return null;
    }

    if (page.results.length === 0) {
      const error = new ApiError({
        code: "demo_missing",
        message: "The demo data hasn't been loaded on this server yet.",
        status: 404,
      });
      dispatch({ type: "analysis/failed", error });
      return null;
    }
    return loadAnalysis(page.results[0].id);
  }, [loadAnalysis, setWakingUp]);

  const retryUpload = useCallback(() => retryUploadRef.current?.(), []);
  const retryAnalysis = useCallback(() => retryAnalysisRef.current?.(), []);

  return { state, uploadResume, analyze, loadAnalysis, loadDemo, retryUpload, retryAnalysis };
}
