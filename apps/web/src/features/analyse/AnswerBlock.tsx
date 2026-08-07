/**
 * The answer, as plain prose with inline numbered references and a citation row beneath.
 * No boxed "finding record" chrome any more: a heading, the text, the references. The
 * answer is set in the UI sans, distinct from the serif-free document, so a generated
 * sentence is never mistaken for contract text.
 */
import { Suspense, lazy } from "react";
import type { AnalyseResponse, Citation } from "../../api/contracts";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonLine, SkeletonText } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";
import { CitationChip } from "./CitationChip";

const EnterOnce = lazy(() => import("../../components/ui/EnterOnce"));

export type AnswerState =
  | { status: "idle"; contractTitle: string | null }
  | { status: "loading" }
  | { status: "error"; error: unknown; onRetry: () => void }
  | { status: "ready"; result: AnalyseResponse };

const EXAMPLES = [
  "What is the cap on liability?",
  "How much notice stops it renewing?",
  "What insurance must the supplier carry?",
];

export function AnswerBlock({
  state,
  activeIndex,
  hoveredIndex,
  onActivate,
  onHover,
  onExample,
}: {
  state: AnswerState;
  activeIndex: number | null;
  hoveredIndex: number | null;
  onActivate: (i: number) => void;
  onHover: (i: number | null) => void;
  onExample: (q: string) => void;
}) {
  if (state.status === "idle") {
    return (
      <EmptyState
        title={state.contractTitle ? "Ask about this contract" : "Open a contract to begin"}
        cause={
          state.contractTitle
            ? "Answers quote the contract and mark the exact clause they came from."
            : "Retrieval is scoped to one agreement at a time."
        }
        action={
          state.contractTitle ? (
            <div className="flex flex-col items-start gap-1.5">
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => onExample(q)}
                  className="text-meta text-accent transition-colors duration-(--duration) hover:text-accent-strong"
                >
                  {q}
                </button>
              ))}
            </div>
          ) : undefined
        }
      />
    );
  }
  if (state.status === "loading") {
    return (
      <div aria-busy>
        <Delayed>
          <div className="flex flex-col gap-4">
            <SkeletonText lines={3} />
            <SkeletonLine width="9rem" />
          </div>
        </Delayed>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <ErrorRegion
        message="Retrieval failed for that question."
        onRetry={state.onRetry}
        hint="Your question is still in the box and the contract is still open."
      />
    );
  }

  const { result } = state;
  if (result.citations.length === 0) {
    return (
      <EmptyState
        title="Nothing matched"
        cause={
          result.answerDetail ??
          "No clause scored for that query. Try naming the commercial term, for example 'liquidated damages' rather than 'what if they are late'."
        }
      />
    );
  }

  const body = (
    <>
      <p className="text-body leading-[1.6] text-ink">
        <Inline answer={result.answer} citations={result.citations} />
      </p>
      {result.answerDetail ? (
        <p className="mt-3 text-meta text-ink-faint">{result.answerDetail}</p>
      ) : null}
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {result.citations.map((c, i) => (
          <CitationChip
            key={c.chunkId}
            index={i}
            citation={c}
            state={i === activeIndex ? "active" : i === hoveredIndex ? "hover" : "idle"}
            onActivate={onActivate}
            onHover={onHover}
          />
        ))}
      </div>
    </>
  );

  return (
    <Suspense fallback={<div>{body}</div>}>
      <EnterOnce>{body}</EnterOnce>
    </Suspense>
  );
}

function Inline({ answer, citations }: { answer: string; citations: readonly Citation[] }) {
  const parts = answer.split(/(\[\d{1,2}\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(\d{1,2})\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const n = Number(m[1]);
        const valid = n >= 1 && n <= citations.length;
        return (
          <sup key={i} className={`num px-0.5 font-semibold ${valid ? "text-accent" : "text-flag"}`}>
            {n}
          </sup>
        );
      })}
    </>
  );
}
