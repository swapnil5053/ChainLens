/**
 * A citation reference under the answer. A small numbered pill that targets a mark in the
 * document. Hover previews the mark; click activates and scrolls to it.
 */
import type { Citation } from "../../api/contracts";
import { clauseLabel } from "../../lib/format";

export function CitationChip({
  index,
  citation,
  state,
  onActivate,
  onHover,
}: {
  index: number;
  citation: Citation;
  state: "idle" | "hover" | "active";
  onActivate: (i: number) => void;
  onHover: (i: number | null) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onActivate(index)}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(index)}
      onBlur={() => onHover(null)}
      aria-pressed={state === "active"}
      aria-label={`Citation ${index + 1}, ${clauseLabel(citation.clauseId, citation.page)}. Show it in the contract.`}
      className={
        "inline-flex min-h-8 items-center gap-1.5 rounded-sm px-2.5 text-meta " +
        "transition-[background-color,color] duration-(--duration) ease-(--ease) " +
        (state === "active"
          ? "bg-accent-weak text-accent"
          : "text-ink-muted hover:bg-panel hover:text-accent")
      }
    >
      <span className="num font-semibold text-accent">{index + 1}</span>
      <span className="num">{clauseLabel(citation.clauseId, citation.page)}</span>
    </button>
  );
}
