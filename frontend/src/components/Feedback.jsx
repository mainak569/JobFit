import { isRetryable } from "../api/client.js";
import { WAKING_UP_MESSAGE } from "../api/wakeNotice.js";

export function WakingUpNotice() {
  return (
    <p className="notice" role="status">
      <span className="notice__pulse" aria-hidden="true" />
      {WAKING_UP_MESSAGE}
    </p>
  );
}

export function ErrorState({ title, error, onRetry }) {
  const canRetry = Boolean(onRetry) && isRetryable(error);
  return (
    <div className="error-state" role="alert">
      <h2 className="error-state__title">{title}</h2>
      <p>{error?.message ?? "Something went wrong."}</p>
      {canRetry && (
        <button type="button" className="button button--secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      {children}
    </div>
  );
}
