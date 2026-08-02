import { StrictMode, Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { shouldRetry } from "./api/queries";
import "./styles/tokens.css";

const client = new QueryClient({
  defaultOptions: {
    queries: { retry: shouldRetry, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

/** Renders the error on screen rather than unmounting to a blank page. */
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  override state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  override render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-[70ch] px-6 py-[10vh] text-body text-ink">
          <p className="mb-2 font-semibold">The interface hit an error while rendering.</p>
          <pre className="overflow-auto rounded bg-panel p-3 text-meta whitespace-pre-wrap">
            {this.state.error.stack ?? this.state.error.message}
          </pre>
          <p className="mt-2 text-ink-muted">
            Copy this and send it back. A common cause is the backend not running or being on
            the wrong port.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

const rootEl = document.getElementById("root")!;
rootEl.setAttribute("data-mounted", "1");
createRoot(rootEl).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);
