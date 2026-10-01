/**
 * WHY a cold-start notice: the API runs on Render's free tier, which puts the
 * server to sleep after 15 idle minutes. The first request after that waits
 * about 50 seconds while it boots. A silent 50-second spinner looks exactly
 * like a broken site, and most visitors leave. Any request still pending after
 * 3 seconds is almost certainly a cold start (a warm request answers in well
 * under a second), so that's when we explain what's happening.
 */

export const SLOW_REQUEST_MS = 3000;

export const WAKING_UP_MESSAGE = "Waking up the server, this takes about a minute on the free tier.";

/** Start the timer; returns a function that cancels it and hides the notice. */
export function startWakeNotice(setWakingUp, delayMs = SLOW_REQUEST_MS) {
  const timer = setTimeout(() => setWakingUp(true), delayMs);
  return function stopWakeNotice() {
    clearTimeout(timer);
    setWakingUp(false);
  };
}

/** Await a request, showing the notice if it takes longer than delayMs. */
export async function withWakeNotice(promise, setWakingUp, delayMs = SLOW_REQUEST_MS) {
  const stopWakeNotice = startWakeNotice(setWakingUp, delayMs);
  try {
    return await promise;
  } finally {
    stopWakeNotice();
  }
}
