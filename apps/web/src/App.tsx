/**
 * The shell. Composes, holds URL state, contains no business logic.
 *
 * The comparison and latency views are lazy, so neither is in the initial bundle behind
 * Analyse, which is the screen a first visit lands on.
 */
import { Suspense, lazy, useState } from "react";
import { getAdapter } from "./api";
import { SkeletonParagraph } from "./components/ui/Skeleton";
import { AnalyseView } from "./features/analyse/AnalyseView";
import { LatencyBadge } from "./features/latency/LatencyBadge";
import { useAppState, type ViewId } from "./lib/url";

const CompareView = lazy(() =>
  import("./features/compare/CompareView").then((module) => ({ default: module.CompareView })),
);
const LatencyView = lazy(() =>
  import("./features/latency/LatencyView").then((module) => ({ default: module.LatencyView })),
);

const TABS: { id: ViewId; label: string }[] = [
  { id: "analyse", label: "Analyse" },
  { id: "compare", label: "Retrieval comparison" },
  { id: "latency", label: "Latency" },
];

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(
    () => (document.documentElement.dataset["theme"] as "light" | "dark") ?? "light",
  );
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset["theme"] = next;
    setTheme(next);
  };
  return { theme, toggle };
}

export function App() {
  const [state, update] = useAppState();
  const { theme, toggle } = useTheme();
  const adapter = getAdapter();

  return (
    <div className="flex h-dvh flex-col">
      <a
        href="#main"
        className="link sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-10 focus:bg-ground focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b-2 border-ink px-4 py-3">
        <h1 className="text-body font-semibold tracking-[0.01em]">ChainLens</h1>
        <span className="numeric rounded-[3px] border border-accent px-[6px] py-[2px] text-micro uppercase tracking-(--tracking-label) text-accent">
          Clause audit
        </span>

        <nav aria-label="Views">
          <ul className="m-0 flex list-none gap-1 p-0">
            {TABS.map((tab) => {
              const active = state.view === tab.id;
              return (
                <li key={tab.id}>
                  <button
                    type="button"
                    onClick={() => update({ view: tab.id })}
                    aria-current={active ? "page" : undefined}
                    className={
                      "min-h-8 rounded-[2px] px-3 text-small transition-colors " +
                      "duration-(--duration-hover) ease-(--ease-enter) " +
                      (active
                        ? "bg-panel-raised text-ink shadow-[inset_0_-2px_0_0_var(--accent)]"
                        : "text-ink-muted hover:bg-panel-raised hover:text-ink")
                    }
                  >
                    {tab.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <LatencyBadge onOpen={() => update({ view: "latency" })} />
          <button
            type="button"
            onClick={toggle}
            aria-pressed={theme === "dark"}
            className="min-h-8 rounded-[2px] border border-rule-control px-3 text-micro uppercase tracking-(--tracking-label) text-ink-muted transition-colors duration-(--duration-hover) ease-(--ease-enter) hover:bg-panel-raised"
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </header>

      <main id="main" className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <Suspense
          fallback={
            <div className="p-4">
              <div className="field p-4">
                <SkeletonParagraph lines={5} />
              </div>
            </div>
          }
        >
          {state.view === "analyse" ? (
            <AnalyseView
              contractId={state.contractId}
              query={state.query}
              onContractChange={(id) => update({ contractId: id })}
              onQueryChange={(value) => update({ query: value })}
            />
          ) : null}
          {state.view === "compare" ? (
            <CompareView contractId={state.contractId} query={state.query} />
          ) : null}
          {state.view === "latency" ? <LatencyView /> : null}
        </Suspense>
      </main>

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-rule px-4 py-2 text-micro text-ink-muted">
        {/* The active data path is never ambiguous. A demo that can be mistaken for live
            data is the only kind that misleads. */}
        <span>
          Data path:{" "}
          <span className="numeric text-ink">{adapter.source === "mock" ? "MOCK" : "LIVE"}</span> -{" "}
          {adapter.describe}
        </span>
        <span className="ml-auto">
          Corpus: 29 CUAD supply-chain contracts, CC BY 4.0, The Atticus Project
        </span>
      </footer>
    </div>
  );
}
