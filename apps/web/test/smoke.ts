/**
 * Correctness smoke test for the two things the interface is trusted on: that a citation
 * span maps to the exact contract text, and that the two retrieval arms genuinely differ.
 *
 * Runs against real fixtures, not stubs. Bundled by esbuild and executed in node, so it
 * needs no browser and no test framework.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ChunkRef, Citation } from "../src/api/contracts";
import { expandQuery } from "../src/api/mock/glossary";
import { MockIndex } from "../src/api/mock/retrieval";
import { buildParagraphs, splitParagraphs } from "../src/lib/marks";

const root = join(import.meta.dirname ?? process.cwd(), "..");
const index = JSON.parse(readFileSync(join(root, "public/fixtures/index.json"), "utf8")) as {
  contracts: { id: string }[];
};

let failures = 0;
function check(label: string, condition: boolean, detail = "") {
  if (condition) console.log(`  PASS  ${label}`);
  else {
    failures += 1;
    console.log(`  FAIL  ${label}${detail ? ` -- ${detail}` : ""}`);
  }
}

console.log(`fixtures: ${index.contracts.length} contracts`);
check("29 contracts in the index", index.contracts.length === 29);

const QUERIES = [
  "What is the cap on liability?",
  "How much notice is needed to stop it renewing?",
  "What insurance must the supplier carry?",
  "DDP obligations",
];

let totalChunks = 0;
let divergent = 0;
let compared = 0;

for (const summary of index.contracts.slice(0, 6)) {
  const document = JSON.parse(
    readFileSync(join(root, `public/fixtures/contracts/${summary.id}.json`), "utf8"),
  ) as { fullText: string; chunks: Record<string, ChunkRef[]> };

  const clause = document.chunks["clause-aware"] ?? [];
  totalChunks += clause.length;

  const badOffsets = clause.filter((chunk) => {
    const sliced = document.fullText.slice(chunk.start, chunk.end);
    return sliced.length === 0 || sliced !== sliced.trim();
  });
  check(
    `${summary.id.slice(0, 34)}: chunk offsets slice cleanly`,
    badOffsets.length === 0,
    `${badOffsets.length} bad of ${clause.length}`,
  );

  const engine = new MockIndex(clause, document.fullText);

  for (const query of QUERIES) {
    const rrf = engine.rrf(expandQuery(query), 6);
    const mmr = engine.mmr(query, 6);
    if (rrf.length === 0 && mmr.length === 0) continue;
    compared += 1;

    const citations: Citation[] = rrf.map((hit) => ({
      chunkId: hit.chunk.id,
      text: hit.text,
      span: { start: hit.chunk.start, end: hit.chunk.end },
      score: hit.score,
      page: hit.chunk.page,
      clauseId: hit.chunk.clauseId,
      clauseTitle: hit.chunk.clauseTitle,
    }));

    // A clause chunk usually straddles several paragraphs, so one citation produces
    // several marks. Each must slice back to its own text and lie inside the cited span.
    // The concatenation is deliberately not compared: the paragraph breaks between
    // segments are structure, not marked content.
    const paragraphs = buildParagraphs(document.fullText, citations);
    for (let i = 0; i < citations.length; i += 1) {
      const span = citations[i]!.span;
      const segments = paragraphs
        .flatMap((paragraph) => paragraph.segments)
        .filter((segment) => segment.citationIndex === i);
      if (segments.length === 0) {
        failures += 1;
        console.log(`  FAIL  citation ${i} produced no mark`);
        continue;
      }
      for (const segment of segments) {
        const exact = document.fullText.slice(segment.start, segment.end) === segment.text;
        const inside = segment.start >= span.start && segment.end <= span.end;
        if (!exact || !inside) {
          failures += 1;
          console.log(
            `  FAIL  mark ${i} at ${segment.start}-${segment.end} ` +
              `${exact ? "escapes its citation span" : "does not slice back to its text"}`,
          );
        }
      }
      const covered = segments.reduce((sum, seg) => sum + (seg.end - seg.start), 0);
      if (covered / (span.end - span.start) < 0.5) {
        failures += 1;
        console.log(`  FAIL  mark ${i} covers under half its cited span`);
      }
    }

    const rrfIds = new Set(rrf.map((hit) => hit.chunk.id));
    if (mmr.filter((hit) => rrfIds.has(hit.chunk.id)).length < Math.max(rrf.length, mmr.length)) {
      divergent += 1;
    }
  }
}

check("paragraph splitting is non-trivial", splitParagraphs("a\n\nb\n\nc").length === 3);
check("glossary expands DDP", expandQuery("DDP terms").includes("delivered duty paid"));
check("glossary leaves unrelated queries alone", expandQuery("hello there") === "hello there");
check("every mark slices back to its text and lies inside its citation", failures === 0);
check(
  `the two arms diverge on most queries (${divergent}/${compared})`,
  compared > 0 && divergent / compared >= 0.5,
);
console.log(`  info  ${totalChunks} clause chunks exercised`);

if (failures > 0) {
  console.log(`\n${failures} failures`);
  process.exit(1);
}
console.log("\nall checks passed");
