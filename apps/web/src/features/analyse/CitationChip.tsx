/**
 * A citation is a target, not a bracketed numeral.
 *
 * Hover raises the corresponding span in the document to a soft mark; click makes it the
 * active mark and scrolls the document to it. The chip reserves its own space whether or
 * not it is hovered, so nothing shifts under the pointer.
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
  onActivate: (index: number) => void;
  onHover: (index: number | null) => void;
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
      aria-label={`Citation ${index + 1}, ${clauseLabel(citation.clauseId, citation.page)}${
        citation.clauseTitle ? `, ${citation.clauseTitle}` : ""
      }. Activate to mark it in the contract.`}
      className={
        "inline-flex min-h-6 shrink-0 items-center gap-2 whitespace-nowrap rounded-[3px] " +
        "border px-2 py-1 text-micro transition-[background-color,border-color,transform] " +
        "duration-(--duration-hover) ease-(--ease-enter) active:translate-y-px " +
        (state === "active"
          ? "border-accent bg-mark text-ink"
          : state === "hover"
            ? "border-accent bg-mark-soft text-ink"
            : "border-rule-control bg-ground text-ink-muted hover:border-accent hover:bg-mark-soft")
      }
    >
      <span className="numeric font-semibold text-accent">{index + 1}</span>
      <span className="numeric">{clauseLabel(citation.clauseId, citation.page)}</span>
    </button>
  );
}
