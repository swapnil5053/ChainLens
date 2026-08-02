export function ms(value: number): string {
  return value >= 100 ? value.toFixed(0) : value.toFixed(1);
}

export function percent(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

export function clauseLabel(clauseId: string | null, page: number): string {
  return clauseId ? `Clause ${clauseId}` : `Page ${page}`;
}

/** Collapse runs of whitespace for single-line display without touching the source. */
export function oneLine(value: string, limit = 160): string {
  const flat = value.replace(/\s+/g, " ").trim();
  return flat.length > limit ? `${flat.slice(0, limit)}...` : flat;
}
