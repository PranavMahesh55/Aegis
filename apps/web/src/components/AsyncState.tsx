import type { ReactNode } from "react";
import { ApiError } from "../api/client";

export function LoadingState({ label = "Loading operational state" }: { label?: string }) {
  return (
    <div className="paper-panel state-panel" role="status">
      <span className="loading-mark" aria-hidden="true" />
      <strong>{label}</strong>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) {
  const apiError = error instanceof ApiError ? error.problem : null;
  return (
    <div className="paper-panel state-panel error-panel" role="alert">
      <p className="eyebrow">Unable to load</p>
      <strong>{apiError?.title ?? "Aegis request failed"}</strong>
      <span>{apiError?.detail ?? error.message}</span>
      {apiError && <code>{apiError.code} · {apiError.traceId}</code>}
      {retry && <button className="secondary" onClick={retry}>Retry</button>}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="paper-panel state-panel">{children}</div>;
}

