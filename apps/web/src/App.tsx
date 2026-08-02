/**
 * The shell. A thin top bar with the name, three tabs, and the theme toggle. No stamp, no
 * live badge, no attribution strip. Comparison and Latency stay lazy so neither is in the
 * initial bundle behind Analyse.
 */
import { Suspense, lazy, useState } from "react";
import { getAdapter } from "./api";
import { SkeletonText } from "./components/ui/Skeleton";
import { AnalyseView } from "./features/analyse/AnalyseView";
import { useAppState, type ViewId } from "./lib/url";

const CompareView = lazy(() =>
  import("./features/compare/CompareView").then((m) => ({ default: m.CompareView })),
);
const LatencyView = lazy(() =>
  import("./features/latency/LatencyView").then((m) => ({ default: m.LatencyView })),
);

const TABS: { id: ViewId; label: string }[] = [
  { id: "analyse", label: "Analyse" },
  { id: "compare", label: "Compare" },
  { id: "latency", label: "Latency" },
];

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(
    () => (document.documentElement.dataset["theme"] as "light" | "dark") ?? "light",
  );
  return {
    theme,
    toggle: () => {
      const next = theme === "dark" ? "light" : "dark";
      document.documentElement.dataset["theme"] = next;
      setTheme(next);
    },
  };
}

export function App() {
  const [state, update] = useAppState();
  const { theme, toggle } = useTheme();
  const live = getAdapter().source === "http";

  return (
    <div className="flex h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-10 focus:bg-ground focus:px-3 focus:py-2 focus:text-accent">
        Skip to content
      </a>

      <header className="flex items-center gap-6 border-b border-line px-6 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-lead font-semibold tracking-tight text-ink">ChainLens</span>
          {live ? <span className="text-meta text-accent">live</span> : null}
        </div>

        <nav aria-label="Views" className="flex gap-1">
          {TABS.map((tab) => {
            const active = state.view === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => update({ view: tab.id })}
                aria-current={active ? "page" : undefined}
                className={
                  "min-h-9 rounded-sm px-3 text-body transition-colors duration-(--duration) " +
                  (active ? "font-medium text-ink" : "text-ink-muted hover:text-ink")
                }
              >
                {tab.label}
                {active ? <span className="mt-1.5 block h-0.5 rounded-full bg-accent" /> : null}
              </button>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={toggle}
          aria-pressed={theme === "dark"}
          className="ml-auto min-h-9 rounded-sm px-3 text-meta text-ink-muted transition-colors duration-(--duration) hover:text-ink"
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </header>

      <main id="main" className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <Suspense fallback={<div className="px-6 py-8"><SkeletonText lines={5} /></div>}>
          {state.view === "analyse" ? (
            <AnalyseView
              contractId={state.contractId}
              query={state.query}
              onContractChange={(id) => update({ contractId: id })}
              onQueryChange={(v) => update({ query: v })}
            />
          ) : null}
          {state.view === "compare" ? <CompareView contractId={state.contractId} query={state.query} /> : null}
          {state.view === "latency" ? <LatencyView /> : null}
        </Suspense>
      </main>
    </div>
  );
}
