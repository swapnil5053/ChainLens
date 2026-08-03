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
  "What are the payment terms?",
  "Who is responsible for damaged or lost goods?",
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
    if (!state.contractTitle) {
      return (
        <EmptyState
          title="No contract open"
          cause="Choose an agreement above, or upload a PDF."
        />
      );
    }
    return (
      <div className="flex flex-col gap-3.5 pt-2">
        <h2 className="text-[19px] font-semibold tracking-tight text-ink">Start with a question</h2>
        <p className="max-w-[40ch] text-meta leading-relaxed text-ink-muted">
          Answers quote the contract and mark the exact clause they came from.
        </p>
        <div className="mt-1 flex flex-col">
          {EXAMPLES.map((q, i) => (
            <button
              key={q}
              type="button"
              onClick={() => onExample(q)}
              className={
                "wipe cursor-pointer bg-transparent px-0.5 py-2.5 text-left text-meta text-ink-muted " +
                (i < EXAMPLES.length - 1 ? "border-b border-line" : "")
              }
            >
              {q}
            </button>
          ))}
        </div>
      </div>
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
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="eyebrow mr-0.5">Sources</span>
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
      {result.answerDetail ? (
        <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-faint">
          {result.answerDetail}
        </p>
      ) : null}
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
