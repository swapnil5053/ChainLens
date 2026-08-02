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
  return (
    <div
      tabIndex={0}
      role="document"
      aria-label={`${state.document.title}, full text`}
      className="h-full overflow-y-auto px-8 py-8"
    >
      <div className="prose mx-auto">
        {paragraphs.map((p) => (
          <p key={p.key} className="mb-5 whitespace-pre-wrap text-body leading-[1.7] text-ink">
            {p.segments.map((seg) =>
              seg.citationIndex === null ? (
                <span key={seg.key}>{seg.text}</span>
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
                  {seg.text}
                </mark>
              ),
            )}
          </p>
        ))}
      </div>
    </div>
  );
}
