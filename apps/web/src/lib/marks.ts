/**
 * Turn a document plus a set of citation spans into renderable segments.
 *
 * The document renders as paragraph slices rather than one enormous text node, so marking
 * a span re-renders a paragraph rather than re-laying out fifty thousand characters.
 * Spans are half-open and may overlap; overlapping spans collapse to the lower citation
 * index, which is the one the reader met first.
 *
 * Every segment carries absolute offsets. That is what lets the smoke test prove a
 * highlight lies inside the span it claims, rather than taking the rendering on trust.
 */
import type { Citation } from "../api/contracts";

export interface Segment {
  key: string;
  text: string;
  start: number;
  end: number;
  citationIndex: number | null;
}

export interface Paragraph {
  key: string;
  start: number;
  end: number;
  segments: Segment[];
  citationIndices: number[];
}

const PARAGRAPH_BREAK = /\n\s*\n/g;

export function splitParagraphs(fullText: string): { start: number; end: number }[] {
  const bounds: { start: number; end: number }[] = [];
  let cursor = 0;
  PARAGRAPH_BREAK.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = PARAGRAPH_BREAK.exec(fullText)) !== null) {
    if (match.index > cursor) bounds.push({ start: cursor, end: match.index });
    cursor = match.index + match[0].length;
  }
  if (cursor < fullText.length) bounds.push({ start: cursor, end: fullText.length });
  return bounds;
}

export function buildParagraphs(fullText: string, citations: readonly Citation[]): Paragraph[] {
  const ranges = citations.map((citation, index) => ({ ...citation.span, index }));
  return splitParagraphs(fullText).map((bounds, paragraphIndex) => {
    const overlapping = ranges
      .filter((range) => range.start < bounds.end && bounds.start < range.end)
      .sort((left, right) => left.start - right.start || left.index - right.index);

    const segments: Segment[] = [];
    let cursor = bounds.start;
    for (const range of overlapping) {
      const from = Math.max(range.start, cursor, bounds.start);
      const to = Math.min(range.end, bounds.end);
      if (to <= from) continue;
      if (from > cursor) {
        segments.push({
          key: `${paragraphIndex}:${cursor}`,
          text: fullText.slice(cursor, from),
          start: cursor,
          end: from,
          citationIndex: null,
        });
      }
      segments.push({
        key: `${paragraphIndex}:${from}:m`,
        text: fullText.slice(from, to),
        start: from,
        end: to,
        citationIndex: range.index,
      });
      cursor = to;
    }
    if (cursor < bounds.end) {
      segments.push({
        key: `${paragraphIndex}:${cursor}`,
        text: fullText.slice(cursor, bounds.end),
        start: cursor,
        end: bounds.end,
        citationIndex: null,
      });
    }
    return {
      key: `p${paragraphIndex}`,
      start: bounds.start,
      end: bounds.end,
      segments,
      citationIndices: [...new Set(overlapping.map((range) => range.index))],
    };
  });
}
