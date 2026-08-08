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
        "inline-flex min-h-8 items-center gap-[7px] rounded-sm border px-2.5 text-[12.5px] font-semibold " +
        "transition-[background-color,border-color,transform,color] duration-(--duration) ease-(--ease) " +
        "hover:-translate-y-px " +
        (state === "active"
          ? "border-lime bg-accent-weak text-[#C6F5AC]"
          : "border-[#3C6B32] bg-accent-weak text-[#A9E88F] hover:border-lime hover:text-[#C6F5AC]")
      }
    >
      <span className="num">{index + 1}</span>
      <span className="font-normal text-ink-muted">
        {clauseLabel(citation.clauseId, citation.page)}
      </span>
    </button>
  );
}
