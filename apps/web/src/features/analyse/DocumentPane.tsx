/**
 * The contract itself, marked in place.
 *
 * Deliberately not virtualized. Documents here top out near 90,000 characters, roughly 400
 * paragraph nodes, which renders fine; virtualizing would break scroll-to-citation because
 * the target paragraph would not be mounted when we try to scroll to it. That trade is
 * written up in docs/taste-pass-analyse.md rather than left as a surprise.
 */
import { useEffect, useRef } from "react";
import type { Citation, ContractDocument } from "../../api/contracts";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonParagraph } from "../../components/ui/Skeleton";
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
  onSelectCitation: (index: number) => void;
}) {
  const markRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (activeIndex === null) return;
    // The mark owns the scroll, not the citation list: scrolling to the element that is
    // actually highlighted is what makes the interaction feel physical. Under
    // prefers-reduced-motion the token layer forces scroll-behavior: auto, so this jumps.
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeIndex, state.status]);

  if (state.status === "idle") {
    return (
      <section className="field flex min-h-0 flex-1 items-start p-6" aria-label="Contract">
        <EmptyState
          title="No contract open"
          cause="Pick an agreement from the corpus list. It renders here in full, and answers mark their citations directly in this text."
        />
      </section>
    );
  }

  if (state.status === "loading") {
    return (
      <section
        className="field min-h-0 flex-1 overflow-hidden p-6"
        aria-busy="true"
        aria-label="Contract"
      >
        <Delayed>
          <div className="mx-auto flex max-w-[95ch] flex-col gap-6">
            <SkeletonParagraph lines={3} />
            <SkeletonParagraph lines={6} />
            <SkeletonParagraph lines={5} />
            <SkeletonParagraph lines={4} />
          </div>
        </Delayed>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="field min-h-0 flex-1 p-6" aria-label="Contract">
        <ErrorRegion
          title="Contract text unavailable"
          error={state.error}
          onRetry={state.onRetry}
          hint="The corpus list still works, so you can open a different agreement while this one is failing."
        />
      </section>
    );
  }

  const paragraphs = buildParagraphs(state.document.fullText, citations);

  return (
    <section className="field flex min-h-0 flex-1 flex-col" aria-label="Contract">
      <header className="flex items-baseline gap-3 border-b border-rule px-4 py-2">
        <h2 className="field-label">Contract</h2>
        <p className="truncate text-small text-ink">{state.document.title}</p>
        <span className="numeric ml-auto shrink-0 text-micro text-ink-faint">
          {state.document.pageCount}pp / {state.document.charCount.toLocaleString()} chars
        </span>
      </header>

      <div
        tabIndex={0}
        role="document"
        aria-label={`${state.document.title}, full text`}
        className="min-h-0 flex-1 overflow-y-auto bg-ground px-6 py-6"
      >
        <div className="mx-auto max-w-[95ch]">
          {paragraphs.map((paragraph) => (
            <p
              key={paragraph.key}
              className="mb-4 whitespace-pre-wrap font-(family-name:--font-document) text-reading leading-[1.6] text-ink"
            >
              {paragraph.segments.map((segment) =>
                segment.citationIndex === null ? (
                  <span key={segment.key}>{segment.text}</span>
                ) : (
                  <mark
                    key={segment.key}
                    ref={segment.citationIndex === activeIndex ? markRef : undefined}
                    className="citation-mark cursor-pointer"
                    data-state={
                      segment.citationIndex === activeIndex
                        ? "active"
                        : segment.citationIndex === hoveredIndex
                          ? "hover"
                          : "idle"
                    }
                    onClick={() => onSelectCitation(segment.citationIndex as number)}
                    title={`Citation ${segment.citationIndex + 1}`}
                  >
                    {segment.text}
                  </mark>
                ),
              )}
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}
