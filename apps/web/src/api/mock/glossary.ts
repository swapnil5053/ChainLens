/**
 * The query-expansion glossary, mirroring apps/api/chainlens/retrieval/glossary.yaml.
 *
 * Duplicated rather than imported because the mock adapter must run with no backend at
 * all. Drift is checked by scripts/check_glossary_parity.py: a term on the client that
 * the server does not have, or expands differently, fails the check rather than silently
 * making the comparison view flatter than the real system.
 */
export const GLOSSARY: Readonly<Record<string, readonly string[]>> = {
  ddp: ["delivered duty paid", "incoterms"],
  dap: ["delivered at place", "incoterms"],
  fob: ["free on board", "incoterms"],
  fca: ["free carrier", "incoterms"],
  cif: ["cost insurance and freight", "incoterms"],
  exw: ["ex works", "incoterms"],
  incoterm: ["incoterms 2020", "delivery term", "trade term"],
  incoterms: ["incoterms 2020", "delivery term", "trade term"],
  sla: ["service level agreement", "service levels", "performance standard"],
  otif: ["on time in full", "delivery performance"],
  demurrage: ["detention", "laytime", "port charges"],
  detention: ["demurrage", "container detention"],
  laytime: ["demurrage", "loading time", "discharge time"],
  bol: ["bill of lading"],
  moq: ["minimum order quantity", "minimum commitment"],
  msa: ["master services agreement", "master agreement"],
  "force majeure": ["act of god", "excusable delay", "events beyond reasonable control"],
  "liability cap": ["limitation of liability", "aggregate liability", "cap on liability"],
  liable: ["limitation of liability", "aggregate liability", "cap on liability"],
  penalty: ["liquidated damages", "service credit", "remedy"],
  penalties: ["liquidated damages", "service credit", "remedy"],
  termination: ["notice period", "notice to terminate", "termination for convenience"],
  terminate: ["notice period", "notice to terminate", "termination for convenience"],
  renew: ["automatic renewal", "renewal term", "evergreen"],
  renewing: ["automatic renewal", "renewal term", "evergreen"],
  renews: ["automatic renewal", "renewal term", "evergreen"],
  governs: ["governing law", "applicable law", "choice of law"],
  jurisdiction: ["venue", "forum", "courts of"],
  payment: ["net 30", "net 60", "invoice", "days from invoice"],
  warranty: ["warranty period", "warranty duration", "defect liability"],
  insurance: ["insurance required", "certificate of insurance", "coverage"],
  audit: ["audit rights", "inspect records", "books and records"],
  assigned: ["assignment", "anti-assignment", "transfer"],
  exclusive: ["exclusivity", "sole distributor", "exclusive right"],
};

export function expandQuery(query: string): string {
  const lowered = query.toLowerCase();
  const additions: string[] = [];
  for (const [term, alternatives] of Object.entries(GLOSSARY)) {
    const hit = term.includes(" ")
      ? lowered.includes(term)
      : new RegExp(`\\b${term}\\b`).test(lowered);
    if (!hit) continue;
    for (const alternative of alternatives) {
      if (!lowered.includes(alternative) && !additions.includes(alternative)) {
        additions.push(alternative);
      }
    }
  }
  return additions.length ? `${query} ${additions.join(" ")}` : query;
}
