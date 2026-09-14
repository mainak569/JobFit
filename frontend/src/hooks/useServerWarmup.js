import { useEffect } from "react";

import { pingHealth } from "../api/client.js";

/**
 * Ping the API once when the app loads.
 *
 * WHY: a sleeping free-tier server takes ~50 seconds to boot. Starting that
 * boot the moment the page opens means it is often already awake by the time
 * someone has found their PDF and pasted a job description.
 */
export function useServerWarmup() {
  useEffect(() => {
    pingHealth().catch(() => {
      // A failed ping is not worth showing; the real request will report it.
    });
  }, []);
}
