/**
 * The shell. One screen: read a contract, ask about it. The retrieval-comparison and
 * latency views were engineering demonstrations, not things a user of a logistics
 * document tool needs, so they are not in the interface. The header is just the name and
 * a theme toggle.
 */
import { useState } from "react";
import { getAdapter } from "./api";
import { AnalyseView } from "./features/analyse/AnalyseView";
import { useAppState } from "./lib/url";

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
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-10 focus:bg-ground focus:px-3 focus:py-2 focus:text-accent"
      >
        Skip to content
      </a>

      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <span className="text-lead font-semibold tracking-tight text-ink">ChainLens</span>
        <span className="text-meta text-ink-faint">contract reader</span>
        {live ? <span className="text-meta text-accent">live</span> : null}
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
        <AnalyseView
          contractId={state.contractId}
          query={state.query}
          onContractChange={(id) => update({ contractId: id })}
          onQueryChange={(v) => update({ query: v })}
        />
      </main>
    </div>
  );
}
