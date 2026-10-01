import { useCallback, useEffect, useReducer, useRef } from "react";

import * as api from "../api/client.js";
import { ApiError } from "../api/client.js";
import { withWakeNotice } from "../api/wakeNotice.js";
import { rememberInterview } from "../lib/interviewStore.js";

// AI requests take several seconds even on a warm server, so the 3-second
// cold-start notice would fire on almost every answer.
const AI_SLOW_REQUEST_MS = 15000;

function notFoundAs(message) {
  return (error) =>
    error.code === "not_found" ? new ApiError({ code: "not_found", message, status: 404 }) : error;
}

const startInitialState = {
  status: "idle", // idle | starting | error
  error: null,
  analysis: null,
  analysisStatus: "idle", // idle | loading | ready | error
  analysisError: null,
  wakingUp: false,
};

function startReducer(state, action) {
  switch (action.type) {
    case "start/started":
      return { ...state, status: "starting", error: null };
    case "start/failed":
      return { ...state, status: "error", error: action.error };
    case "start/done":
      return { ...state, status: "idle" };
    case "analysis/started":
      return { ...state, analysis: null, analysisStatus: "loading", analysisError: null };
    case "analysis/ready":
      return { ...state, analysis: action.analysis, analysisStatus: "ready" };
    case "analysis/failed":
      return { ...state, analysisStatus: "error", analysisError: action.error };
    case "analysis/cleared":
      return { ...state, analysis: null, analysisStatus: "idle", analysisError: null };
    case "wakingUp/changed":
      return { ...state, wakingUp: action.wakingUp };
    default:
      throw new Error(`Unknown action: ${action.type}`);
  }
}

export function useStartInterview() {
  const [state, dispatch] = useReducer(startReducer, startInitialState);

  const setWakingUp = useCallback((wakingUp) => {
    dispatch({ type: "wakingUp/changed", wakingUp });
  }, []);

  const loadAnalysis = useCallback(
    async (analysisId) => {
      dispatch({ type: "analysis/started" });
      try {
        const analysis = await withWakeNotice(api.getAnalysis(analysisId), setWakingUp);
        dispatch({ type: "analysis/ready", analysis });
      } catch (error) {
        const shown = notFoundAs("That analysis doesn't exist any more. It may have been deleted.")(error);
        dispatch({ type: "analysis/failed", error: shown });
      }
    },
    [setWakingUp]
  );

  const clearAnalysis = useCallback(() => dispatch({ type: "analysis/cleared" }), []);

  const start = useCallback(
    async (payload) => {
      dispatch({ type: "start/started" });
      try {
        const session = await withWakeNotice(api.startInterview(payload), setWakingUp, AI_SLOW_REQUEST_MS);
        rememberInterview(session);
        dispatch({ type: "start/done" });
        return session;
      } catch (error) {
        dispatch({ type: "start/failed", error });
        return null;
      }
    },
    [setWakingUp]
  );

  return { state, loadAnalysis, clearAnalysis, start };
}

const sessionInitialState = {
  session: null,
  status: "loading", // loading | ready | error
  error: null,
  pending: null, // null | "answer" | "finish"
  actionError: null,
  failedAction: null, // "answer" | "finish"
  wakingUp: false,
};

function sessionReducer(state, action) {
  switch (action.type) {
    case "load/started":
      return { ...sessionInitialState };
    case "load/failed":
      return { ...state, status: "error", error: action.error };
    case "session/updated":
      return { ...state, session: action.session, status: "ready", pending: null };
    case "action/started":
      return { ...state, pending: action.pending, actionError: null, failedAction: null };
    case "action/failed":
      return { ...state, pending: null, actionError: action.error, failedAction: state.pending };
    case "wakingUp/changed":
      return { ...state, wakingUp: action.wakingUp };
    default:
      throw new Error(`Unknown action: ${action.type}`);
  }
}

export function useInterview(interviewId) {
  const [state, dispatch] = useReducer(sessionReducer, sessionInitialState);
  const sessionRef = useRef(null);
  useEffect(() => {
    sessionRef.current = state.session;
  }, [state.session]);

  const setWakingUp = useCallback((wakingUp) => {
    dispatch({ type: "wakingUp/changed", wakingUp });
  }, []);

  const showSession = useCallback((session) => {
    rememberInterview(session);
    dispatch({ type: "session/updated", session });
  }, []);

  const load = useCallback(async () => {
    dispatch({ type: "load/started" });
    try {
      const session = await withWakeNotice(api.getInterview(interviewId), setWakingUp);
      showSession(session);
    } catch (error) {
      const shown = notFoundAs("That interview doesn't exist any more. It may have been deleted.")(error);
      dispatch({ type: "load/failed", error: shown });
    }
  }, [interviewId, setWakingUp, showSession]);

  useEffect(() => {
    load();
  }, [load]);

  const finish = useCallback(async () => {
    dispatch({ type: "action/started", pending: "finish" });
    try {
      const session = await withWakeNotice(api.finishInterview(interviewId), setWakingUp, AI_SLOW_REQUEST_MS);
      showSession(session);
    } catch (error) {
      dispatch({ type: "action/failed", error });
    }
  }, [interviewId, setWakingUp, showSession]);

  /** Resolves true once saved, so the page can clear the box. */
  const sendAnswer = useCallback(
    async (text) => {
      const current = sessionRef.current;
      dispatch({ type: "action/started", pending: "answer" });
      let session;
      try {
        session = await withWakeNotice(
          api.submitAnswer(interviewId, { text, turn: current.turn }),
          setWakingUp,
          AI_SLOW_REQUEST_MS
        );
      } catch (error) {
        if (error.code === "turn_conflict" || error.code === "interview_finished") {
          try {
            showSession(await api.getInterview(interviewId));
          } catch {
            // The conflict message below is enough.
          }
        }
        dispatch({ type: "action/failed", error });
        return false;
      }
      showSession(session);
      if (session.questions_done && session.status === "in_progress") {
        finish();
      }
      return true;
    },
    [interviewId, setWakingUp, showSession, finish]
  );

  const transcribe = useCallback(
    async (recording) => (await api.transcribeAnswer(interviewId, recording)).text,
    [interviewId]
  );

  return { state, reload: load, sendAnswer, finish, transcribe };
}
