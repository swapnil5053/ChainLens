/**
 * The answer as a finding record, not a chat turn.
 *
 * A bordered field block with a letterspaced label, the answer set in the interface
 * grotesque rather than the document serif so a generated sentence can never be mistaken
 * for contract text, and a numbered citation row underneath that reserves its height
 * whether or not there are citations.
 */
import { Suspense, lazy } from "react";
import type { AnalyseResponse, Citation } from "../../api/contracts";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonLine, SkeletonParagraph } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";
import { ms, percent } from "../../lib/format";
import { CitationChip } from "./CitationChip";

const EnterOnce = lazy(() => import("../../components/ui/EnterOnce"));

export type AnswerState =
  | { status: "idle"; contractTitle: string | null }
  | { status: "loading" }
  | { status: "error"; error: unknown; onRetry: () => void }
  | { status: "ready"; result: AnalyseResponse };

const EXAMPLES = [
  "What is the cap on liability?",
  "How much notice is needed to stop it renewing?",
  "What insurance must the supplier carry?",
];

export function AnswerRecord({
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
  onActivate: (index: number) => void;
  onHover: (index: number | null) => void;
  onExample: (query: string) => void;
}) {
  if (state.status === "idle") {
    return (
      <div className="field p-4">
        <p className="field-label">Finding</p>
        <div className="mt-3">
          <EmptyState
            title="Nothing asked yet"
            cause={
              state.contractTitle
                ? `Ask a clause-level question about ${state.contractTitle}. The answer quotes the contract and marks the span it came from.`
                : "Open a contract, then ask a clause-level question about it."
            }
            action={
              <div className="flex flex-col items-start gap-1">
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    className="link text-small"
                    onClick={() => onExample(example)}
                  >
                    {example}
                  </button>
                ))}
              </div>
            }
          />
        </div>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="field p-4" aria-busy="true" aria-label="Retrieving">
        <p className="field-label">Finding</p>
        <Delayed>
          <div className="mt-3 flex flex-col gap-3">
            <SkeletonParagraph lines={3} />
            <div className="flex gap-2 pt-1">
              <SkeletonLine width="7rem" />
              <SkeletonLine width="7rem" />
            </div>
          </div>
        </Delayed>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <ErrorRegion
        title="Retrieval failed"
        error={state.error}
        onRetry={state.onRetry}
        hint="Your question is still in the box. The contract is still open and readable."
      />
    );
  }

  const { result } = state;
  const total = result.timing.embedMs + result.timing.retrieveMs + result.timing.generateMs;

  if (result.citations.length === 0) {
    return (
      <div className="field p-4">
        <p className="field-label">Finding</p>
        <div className="mt-3">
          <EmptyState
            title="Nothing retrieved"
            cause={
              result.answerDetail ??
              "No clause in this contract scored above zero for that query. Try naming the commercial term rather than the concept: 'liquidated damages' rather than 'what happens if they are late'."
            }
          />
        </div>
      </div>
    );
  }

  const body = (
    <RecordBody
      result={result}
      total={total}
      activeIndex={activeIndex}
      hoveredIndex={hoveredIndex}
      onActivate={onActivate}
      onHover={onHover}
    />
  );

  // Enter cheap, once, when the record first has content. The fallback is the same markup
  // without the wrapper, so a slow chunk shows the answer rather than a gap.
  return (
    <Suspense fallback={<div className="field p-4">{body}</div>}>
      <EnterOnce className="field p-4">{body}</EnterOnce>
    </Suspense>
  );
}

function RecordBody({
  result,
  total,
  activeIndex,
  hoveredIndex,
  onActivate,
  onHover,
}: {
  result: AnalyseResponse;
  total: number;
  activeIndex: number | null;
  hoveredIndex: number | null;
  onActivate: (index: number) => void;
  onHover: (index: number | null) => void;
}) {
  return (
    <>
      <div className="flex items-baseline gap-3">
        <p className="field-label">Finding</p>
        <span className="numeric ml-auto text-micro text-ink-faint">
          {ms(total)} ms - embed {percent(result.timing.embedMs, total)}%
        </span>
      </div>

      <p className="mt-3 text-body leading-[1.55] text-ink">
        <InlineAnswer answer={result.answer} citations={result.citations} />
      </p>

      {result.answerDetail ? (
        <p className="mt-3 border-l-2 border-rule-control pl-3 text-micro text-ink-muted">
          {result.answerDetail}
        </p>
      ) : null}

      <div className="mt-4">
        <p className="field-label">Citations</p>
        {/* The row reserves its height and scrolls rather than wrapping, so resolving an
            answer never changes the height of the record. */}
        <div className="mt-2 flex min-h-9 items-center gap-2 overflow-x-auto pb-1">
          {result.citations.map((citation, index) => (
            <CitationChip
              key={citation.chunkId}
              index={index}
              citation={citation}
              state={index === activeIndex ? "active" : index === hoveredIndex ? "hover" : "idle"}
              onActivate={onActivate}
              onHover={onHover}
            />
          ))}
        </div>
      </div>
    </>
  );
}

/** Renders [n] markers in the answer as superscript references to the chips. */
function InlineAnswer({ answer, citations }: { answer: string; citations: readonly Citation[] }) {
  const parts = answer.split(/(\[\d{1,2}\])/g);
  return (
    <>
      {parts.map((part, index) => {
        const match = /^\[(\d{1,2})\]$/.exec(part);
        if (!match) return <span key={index}>{part}</span>;
        const number = Number(match[1]);
        const valid = number >= 1 && number <= citations.length;
        return (
          <sup
            key={index}
            className={`numeric px-[2px] ${valid ? "text-accent" : "text-flag"}`}
            title={valid ? undefined : "citation refers to a passage that was not retrieved"}
          >
            {number}
          </sup>
        );
      })}
    </>
  );
}
