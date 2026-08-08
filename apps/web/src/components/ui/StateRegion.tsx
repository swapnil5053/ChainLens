/**
 * Region-scoped error and empty states. Errors render where the failure happened with a
 * retry for that region, never a global toast. Empty states name the cause and the next
 * action, so "No data" never appears.
 */
import type { ReactNode } from "react";

export function ErrorRegion({
  message,
  onRetry,
  hint,
}: {
  message: string;
  onRetry?: () => void;
  hint?: string;
}) {
  return (
    <div role="alert" className="py-1">
      <p className="eyebrow text-flag">Something went wrong</p>
      <p className="mt-1 text-body text-ink">{message}</p>
      {hint ? <p className="mt-1 text-meta text-ink-muted">{hint}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 text-meta font-medium text-accent transition-colors duration-(--duration) hover:text-accent-strong"
        >
          Try again
        </button>
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
    <div className="max-w-[54ch] py-2">
      <p className="text-body font-medium text-ink">{title}</p>
      <p className="mt-1 text-meta text-ink-muted">{cause}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
