/**
 * The reader shell. One screen: read a contract, ask about it.
 *
 * The chrome is deliberately quieter than the landing page. There is one faint arc behind
 * the header and nothing else moves: this is a working surface, and density and legibility
 * matter more here than atmosphere. The wordmark goes back to the landing page.
 */
import { AnalyseView } from "./features/analyse/AnalyseView";
import { useAppState } from "./lib/url";

function HeaderArc() {
  return (
    <svg
      viewBox="0 0 1440 420"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="pointer-events-none absolute left-0 top-0 h-[300px] w-full opacity-55"
    >
      <defs>
        <linearGradient id="rdFade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#6FBE8F" stopOpacity="0" />
          <stop offset="50%" stopColor="#8CF0B8" stopOpacity=".8" />
          <stop offset="100%" stopColor="#6FBE8F" stopOpacity="0" />
        </linearGradient>
        <filter id="rdBlurL" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="34" />
        </filter>
        <filter id="rdBlurS" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.4" />
        </filter>
      </defs>
      <g fill="none" stroke="url(#rdFade)">
        <path d="M -200 40 Q 720 460 1640 40" strokeWidth="60" opacity=".08" filter="url(#rdBlurL)" />
        <path d="M -200 40 Q 720 460 1640 40" strokeWidth="1.4" opacity=".3" filter="url(#rdBlurS)" />
      </g>
    </svg>
  );
}

export function App() {
  const [state, update] = useAppState();

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden bg-ground">
      <HeaderArc />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-20 focus:bg-panel-raised focus:px-3 focus:py-2 focus:text-accent"
      >
        Skip to content
      </a>

      <main id="main" className="relative z-10 flex min-h-0 flex-1 flex-col overflow-hidden">
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
