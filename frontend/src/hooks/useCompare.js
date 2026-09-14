import { useCallback, useEffect, useRef, useState } from "react";

import * as api from "../api/client.js";
import { withWakeNotice } from "../api/wakeNotice.js";

export function useCompare(resumeId) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const [wakingUp, setWakingUp] = useState(false);
  // Only the newest request may write to state (see useHistory).
  const latestRequest = useRef(0);

  const load = useCallback(async () => {
    latestRequest.current += 1;
    const requestNumber = latestRequest.current;
    setState({ status: "loading", data: null, error: null });
    try {
      const data = await withWakeNotice(api.compareResume(resumeId), setWakingUp);
      if (requestNumber !== latestRequest.current) return;
      setState({ status: "ready", data, error: null });
    } catch (error) {
      if (requestNumber !== latestRequest.current) return;
      setState({ status: "error", data: null, error });
    }
  }, [resumeId]);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, wakingUp, retry: load };
}
