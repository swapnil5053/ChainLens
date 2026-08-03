/**
 * The contract, marked in place. Not virtualized: documents top out near 90k characters
 * (~400 paragraphs) which renders fine, and virtualizing would break scroll-to-citation
 * because the target paragraph would not be mounted. Rendered as paragraph slices so
 * marking a span re-renders one paragraph, not the whole document.
 */
import { useEffect, useRef } from "react";
import type { Citation, ContractDocument } from "../../api/contracts";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonText } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";
import { buildParagraphs } from "../../lib/marks";

export type DocumentPaneState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: unknown; onRetry: () => void }
  | { status: "ready"; document: ContractDocument };

export function DocumentPane({
  state,
  citations,
  activeIndex,
  hoveredIndex,
  onSelectCitation,
}: {
  state: DocumentPaneState;
  citations: readonly Citation[];
  activeIndex: number | null;
  hoveredIndex: number | null;
  onSelectCitation: (i: number) => void;
}) {
  const markRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (activeIndex !== null) markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeIndex, state.status]);

  if (state.status === "idle") {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <EmptyState
          title="No contract open"
          cause="Choose an agreement above. It renders here in full, and any answer marks the exact clause it cites right in this text."
        />
      </div>
    );
  }
  if (state.status === "loading") {
    return (
      <div className="h-full overflow-hidden px-8 py-8">
        <Delayed>
          <div className="prose mx-auto flex flex-col gap-7">
            <SkeletonText lines={3} />
            <SkeletonText lines={6} />
            <SkeletonText lines={5} />
          </div>
        </Delayed>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="px-8 py-8">
        <ErrorRegion
          message="This contract's text could not be loaded."
          onRetry={state.onRetry}
          hint="You can pick a different agreement while this one is failing."
        />
      </div>
    );
  }

  const paragraphs = buildParagraphs(state.document.fullText, citations);
  // PDF extraction leaves a hard line break at the end of every wrapped line, so a
  // paragraph would otherwise render as a tall stack of short ragged lines. Collapse the
  // single newlines inside a paragraph to spaces at render time and let the column reflow.
  // Blank-line paragraph breaks are already gone (splitParagraphs consumed them), and the
  // marks keep their offsets, so this only changes how the text wraps, not what it cites.
  const flow = (text: string) => text.replace(/\s*\n\s*/g, " ");
  return (
    <div
      tabIndex={0}
      role="document"
      aria-label={`${state.document.title}, full text`}
      className="h-full overflow-y-auto px-[clamp(24px,5vw,72px)] py-[clamp(22px,3vw,40px)] pb-24"
    >
      <div className="prose">
        <p className="eyebrow mb-1.5">Agreement</p>
        <h1 className="mb-1.5 text-2xl font-semibold leading-tight tracking-tight text-ink">
          {state.document.title}
        </h1>
        <p className="mb-8 text-meta text-ink-faint">
          {state.document.pageCount} pages &middot; {state.document.charCount.toLocaleString()}{" "}
          characters
        </p>
        {paragraphs.map((p) => (
          <p key={p.key} className="mb-[18px] text-body leading-[1.85] text-ink-read">
            {p.segments.map((seg) =>
              seg.citationIndex === null ? (
                <span key={seg.key}>{flow(seg.text)}</span>
              ) : (
                <mark
                  key={seg.key}
                  ref={seg.citationIndex === activeIndex ? markRef : undefined}
                  className="cite"
                  data-state={
                    seg.citationIndex === activeIndex
                      ? "active"
                      : seg.citationIndex === hoveredIndex
                        ? "hover"
                        : "idle"
                  }
                  onClick={() => onSelectCitation(seg.citationIndex as number)}
                >
                  {flow(seg.text)}
                </mark>
              ),
            )}
          </p>
        ))}
      </div>
    </div>
  );
}
