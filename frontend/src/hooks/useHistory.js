import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import * as api from "../api/client.js";
import { withWakeNotice } from "../api/wakeNotice.js";
import { jobLabel } from "../lib/format.js";

const initialState = {
  status: "loading", // loading | ready | error
  items: [],
  nextPage: null,
  error: null,
  loadingMore: false,
  loadMoreError: null,
  // analysisId -> { item, index }: rows removed optimistically and not yet
  // confirmed by the server, kept so a failed delete can be put back.
  pendingDeletes: {},
  deleteError: null,
};

function withoutKey(object, keyToRemove) {
  const copy = { ...object };
  delete copy[keyToRemove];
  return copy;
}

function reducer(state, action) {
  switch (action.type) {
    case "load/started":
      return initialState;
    case "loadMore/started":
      return { ...state, loadingMore: true, loadMoreError: null };
    case "load/succeeded": {
      const items = action.page === 1 ? action.items : [...state.items, ...action.items];
      return { ...state, status: "ready", items, nextPage: action.nextPage, loadingMore: false };
    }
    case "load/failed":
      if (action.page === 1) {
        return { ...state, status: "error", error: action.error };
      }
      return { ...state, loadingMore: false, loadMoreError: action.error };
    case "delete/optimistic": {
      const index = state.items.findIndex((item) => item.id === action.analysisId);
      if (index === -1) {
        return state;
      }
      return {
        ...state,
        items: state.items.filter((item) => item.id !== action.analysisId),
        pendingDeletes: { ...state.pendingDeletes, [action.analysisId]: { item: state.items[index], index } },
        deleteError: null,
      };
    }
    case "delete/confirmed":
      return { ...state, pendingDeletes: withoutKey(state.pendingDeletes, action.analysisId) };
    case "delete/rolledBack": {
      const removed = state.pendingDeletes[action.analysisId];
      if (!removed) {
        return state;
      }
      const items = [...state.items];
      // Other rows may have been deleted in the meantime, so clamp the index.
      items.splice(Math.min(removed.index, items.length), 0, removed.item);
      return {
        ...state,
        items,
        pendingDeletes: withoutKey(state.pendingDeletes, action.analysisId),
        deleteError: { jobTitle: jobLabel(removed.item.job_description), message: action.error.message },
      };
    }
    default:
      throw new Error(`Unknown action: ${action.type}`);
  }
}

export function useHistory(resumeId) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [wakingUp, setWakingUp] = useState(false);
  // WHY a request counter: switching resumes quickly can leave an older, slower
  // request finishing last. Only the newest request may write to state.
  const latestRequest = useRef(0);

  const loadPage = useCallback(
    async (page) => {
      latestRequest.current += 1;
      const requestNumber = latestRequest.current;
      dispatch({ type: page === 1 ? "load/started" : "loadMore/started" });
      try {
        const data = await withWakeNotice(api.listAnalyses(resumeId, page), setWakingUp);
        if (requestNumber !== latestRequest.current) return;
        dispatch({
          type: "load/succeeded",
          page,
          items: data.results,
          nextPage: data.next ? page + 1 : null,
        });
      } catch (error) {
        if (requestNumber !== latestRequest.current) return;
        dispatch({ type: "load/failed", page, error });
      }
    },
    [resumeId]
  );

  useEffect(() => {
    loadPage(1);
  }, [loadPage]);

  const deleteAnalysis = useCallback(async (analysisId) => {
    // WHY optimistic: deletes almost always succeed, and a row that sits there
    // for a second (or fifty, on a cold start) after clicking Delete feels
    // broken. The row disappears immediately; if the server refuses, it goes
    // back where it was with a message saying why.
    dispatch({ type: "delete/optimistic", analysisId });
    try {
      await api.deleteAnalysis(analysisId);
      dispatch({ type: "delete/confirmed", analysisId });
    } catch (error) {
      if (error.code === "not_found") {
        // Already gone on the server: that's the outcome the user asked for.
        dispatch({ type: "delete/confirmed", analysisId });
        return;
      }
      dispatch({ type: "delete/rolledBack", analysisId, error });
    }
  }, []);

  return {
    ...state,
    wakingUp,
    retry: () => loadPage(1),
    loadMore: () => loadPage(state.nextPage),
    deleteAnalysis,
  };
}
