/**
 * Region-scoped error and empty states.
 *
 * Errors render where the failure happened, with a retry for that region only, never as a
 * global toast: a toast tells the user something broke and takes away the one thing that
 * would tell them what. Empty states name the cause and the next action, so the string
 * "No data" cannot appear anywhere in this application.
 */
import type { ReactNode } from "react";
import { Button } from "./Button";

export function ErrorRegion({
  title,
  error,
  onRetry,
  hint,
}: {
  title: string;
  error: unknown;
  onRetry?: () => void;
  hint?: string;
}) {
  const message =
    error instanceof Error ? error.message : typeof error === "string" ? error : "unknown error";
  const issues =
    error && typeof error === "object" && "issues" in error && Array.isArray(error.issues)
      ? (error.issues as string[])
      : null;

  return (
    <div role="alert" className="field border-t-flag p-4">
      <p className="field-label">{title}</p>
      <p className="mt-2 text-small text-ink">{message}</p>
      {issues ? (
        <ul className="numeric mt-2 list-inside list-disc text-micro text-ink-muted">
          {issues.slice(0, 4).map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      ) : null}
      {hint ? <p className="mt-2 text-small text-ink-muted">{hint}</p> : null}
      {onRetry ? (
        <div className="mt-3">
          <Button onClick={onRetry}>Retry</Button>
        </div>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  cause,
  action,
}: {
  title: string;
  cause: string;
  action?: ReactNode;
}) {
  return (
    <div className="border border-dashed border-rule-control p-6">
      <p className="field-label">{title}</p>
      <p className="mt-2 max-w-[52ch] text-small text-ink-muted">{cause}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
