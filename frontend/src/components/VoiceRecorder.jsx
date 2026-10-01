import { useCallback, useEffect, useRef, useState } from "react";

import { MAX_RECORDING_SECONDS } from "../lib/limits.js";

// Chrome, Edge, Firefox and Brave record webm; Safari records mp4.
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
const MIN_RECORDING_MS = 700;

function canRecord() {
  return typeof window !== "undefined" && Boolean(window.MediaRecorder && navigator.mediaDevices?.getUserMedia);
}

function pickMimeType() {
  return MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

function formatSeconds(total) {
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function micErrorMessage(error) {
  if (error.name === "NotAllowedError" || error.name === "SecurityError") {
    return "Microphone access is blocked. Allow it in the browser's site settings to record.";
  }
  if (error.name === "NotFoundError") {
    return "No microphone was found.";
  }
  return "Couldn't start the microphone. You can still type your answer.";
}

function MicIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/** Records a spoken answer and hands back the transcript through onText. */
export default function VoiceRecorder({ transcribe, onText, onStatusChange, disabled }) {
  const [status, setStatus] = useState("idle"); // idle | recording | transcribing
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState(null);
  const recorderRef = useRef(null);
  const unmountedRef = useRef(false);

  // The recorder's onstop handler takes it from here; with nothing to stop, just reset.
  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    } else {
      setStatus("idle");
    }
  }, []);

  useEffect(() => {
    onStatusChange?.(status);
  }, [status, onStatusChange]);

  // Release the microphone if the page closes mid-recording. The flag is reset on
  // mount because React's development mode mounts every component twice.
  useEffect(() => {
    unmountedRef.current = false;
    return () => {
      unmountedRef.current = true;
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
    };
  }, []);

  useEffect(() => {
    if (status !== "recording") return undefined;
    const startedAt = Date.now();
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_RECORDING_SECONDS) {
        stop();
      }
    }, 250);
    return () => clearInterval(timer);
  }, [status, stop]);

  if (!canRecord()) {
    return null;
  }

  async function handleRecorded(recording) {
    setStatus("transcribing");
    try {
      const text = await transcribe(recording);
      if (text) {
        onText(text);
      } else {
        setError("Didn't catch any words. Try again a little closer to the microphone.");
      }
    } catch (transcribeError) {
      setError(transcribeError.message);
    } finally {
      setStatus("idle");
    }
  }

  async function start() {
    setError(null);
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (micError) {
      setError(micErrorMessage(micError));
      return;
    }

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks = [];
    const startedAt = Date.now();

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      if (unmountedRef.current) return;
      if (Date.now() - startedAt < MIN_RECORDING_MS) {
        setStatus("idle");
        setError("That was too short. Speak for a moment longer.");
        return;
      }
      handleRecorded(new Blob(chunks, { type: recorder.mimeType || mimeType || "audio/webm" }));
    };

    recorderRef.current = recorder;
    recorder.start();
    setSeconds(0);
    setStatus("recording");
  }

  return (
    <div className="recorder">
      {status === "recording" ? (
        <button
          type="button"
          className="button button--secondary button--small recorder__button--on"
          onClick={stop}
        >
          <span className="recorder__dot" aria-hidden="true" />
          Stop recording · {formatSeconds(seconds)}
        </button>
      ) : (
        <button
          type="button"
          className="button button--secondary button--small"
          onClick={start}
          disabled={disabled || status === "transcribing"}
        >
          <MicIcon />
          {status === "transcribing" ? "Turning speech into text…" : "Record answer"}
        </button>
      )}
      <p className="hint" aria-live="polite">
        {status === "recording" && `Recording. Stops by itself after ${MAX_RECORDING_SECONDS / 60} minutes.`}
      </p>
      {error && <p className="inline-error">{error}</p>}
    </div>
  );
}
