import { useEffect, useRef, useState } from "react";

// Browser speech-to-text: free, but missing in Firefox, where the button is hidden.
// Brave has the API but no speech service behind it, so it never hears anything.
const isBrave = typeof navigator !== "undefined" && Boolean(navigator.brave);
const SpeechRecognition =
  typeof window === "undefined" || isBrave ? undefined : window.SpeechRecognition || window.webkitSpeechRecognition;

const ERROR_MESSAGES = {
  "not-allowed": "Microphone access is blocked. Allow it in the browser's site settings to dictate.",
  "service-not-allowed": "This browser doesn't allow dictation here. You can still type your answer.",
  "audio-capture": "No microphone was found.",
  network: "Dictation needs an internet connection to the browser's speech service. You can still type.",
};

export default function DictationButton({ onText, disabled }) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState(null);
  const recognitionRef = useRef(null);
  const onTextRef = useRef(onText);

  useEffect(() => {
    onTextRef.current = onText;
  }, [onText]);

  useEffect(() => {
    if (disabled) {
      recognitionRef.current?.stop();
    }
  }, [disabled]);

  useEffect(() => () => recognitionRef.current?.abort(), []);

  if (!SpeechRecognition) {
    return null;
  }

  function start() {
    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let pending = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0].transcript.trim();
        if (result.isFinal) {
          if (transcript) onTextRef.current(transcript);
        } else {
          pending += ` ${transcript}`;
        }
      }
      setInterim(pending.trim());
    };
    recognition.onerror = (event) => {
      if (event.error !== "aborted" && event.error !== "no-speech") {
        setError(ERROR_MESSAGES[event.error] ?? "Dictation stopped unexpectedly. You can start it again or type.");
      }
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setListening(false);
      setInterim("");
    };

    setError(null);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }

  function toggle() {
    if (listening) {
      recognitionRef.current?.stop();
    } else {
      start();
    }
  }

  return (
    <div className="dictation">
      <button
        type="button"
        className={listening ? "button button--secondary button--small dictation__button--on" : "button button--secondary button--small"}
        onClick={toggle}
        disabled={disabled}
        aria-pressed={listening}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        {listening ? "Stop dictation" : "Dictate"}
      </button>
      <p className="hint" aria-live="polite">
        {listening && (interim ? `Hearing: ${interim}` : "Listening… speak your answer.")}
      </p>
      {error && <p className="inline-error">{error}</p>}
    </div>
  );
}
