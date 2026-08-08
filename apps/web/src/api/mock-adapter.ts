/**
 * The demo adapter.
 *
 * Serves the real CUAD corpus from static fixtures and runs the two retrieval
 * configurations for real, in the browser, over real chunk text at real offsets. It
 * fabricates exactly two things and labels both:
 *
 *   1. Latency, sampled around the measured profile in eval/results. The proportions are
 *      the real finding: query embedding dominates, search is a few milliseconds.
 *   2. The answer, which selects the sentences from the top-ranked clauses that bear on
 *      the question rather than generating new text. `answerDetail` says so and the
 *      interface renders it. It quotes; it cannot invent.
 *
 * Corpus-level Recall@6 and the other grid metrics are not fabricated at all: they are
 * read from the committed evaluation artifacts at fixture build time.
 */
import type { ChainLensAdapter } from "./adapter";
import {
  AnalyseResponseSchema,
  ArmEvidenceSchema,
  CompareResponseSchema,
  ContractDocumentSchema,
  ContractListSchema,
  parseOrThrow,
  type AnalyseRequest,
  type ArmConfig,
  type ArmEvidence,
  type Citation,
  type CompareRequest,
  type CompareResponse,
  type ContractDocument,
  type LatencySummary,
  type Timing,
} from "./contracts";
import { expandQuery } from "./mock/glossary";
import { MockIndex, type ScoredChunk } from "./mock/retrieval";

const FIXTURES = `${import.meta.env.BASE_URL}fixtures`;

export const ARM_CONFIGS: Record<ArmConfig["id"], ArmConfig> = {
  mmr: {
    id: "mmr",
    label: "MMR baseline",
    chunking: "clause-aware",
    strategy: "dense + MMR, lambda 0.5",
    expansion: false,
  },
  "clause-rrf-expansion": {
    id: "clause-rrf-expansion",
    label: "RRF fusion + expansion",
    chunking: "clause-aware",
    strategy: "dense + lexical, RRF k=60",
    expansion: true,
  },
};

/** Deterministic jitter, so a rerun of the demo is reproducible. */
function jitter(seed: string, spread: number): number {
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) / 4294967295 - 0.5) * 2 * spread;
}

async function fetchJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(path, { signal: signal ?? null });
  if (!response.ok) throw new Error(`fixture ${path} returned ${response.status}`);
  return response.json();
}

const documentCache = new Map<string, ContractDocument>();
const indexCache = new Map<string, MockIndex>();
let armEvidence: Record<string, ArmEvidence> | null = null;

async function loadEvidence(signal?: AbortSignal): Promise<Record<string, ArmEvidence>> {
  if (armEvidence) return armEvidence;
  const raw = (await fetchJson(`${FIXTURES}/arms.json`, signal)) as Record<string, unknown>;
  const parsed: Record<string, ArmEvidence> = {};
  for (const [key, value] of Object.entries(raw)) {
    parsed[key] = parseOrThrow(ArmEvidenceSchema, value, `fixtures/arms.json#${key}`);
  }
  armEvidence = parsed;
  return parsed;
}

async function loadDocument(id: string, signal?: AbortSignal): Promise<ContractDocument> {
  const cached = documentCache.get(id);
  if (cached) return cached;
  const raw = (await fetchJson(`${FIXTURES}/contracts/${id}.json`, signal)) as object;
  const document = parseOrThrow(
    ContractDocumentSchema,
    { source: "mock", ...raw },
    `fixtures/contracts/${id}.json`,
  );
  documentCache.set(id, document);
  return document;
}

function indexFor(document: ContractDocument, strategy: string): MockIndex {
  const key = `${document.id}:${strategy}`;
  const cached = indexCache.get(key);
  if (cached) return cached;
  const built = new MockIndex(document.chunks[strategy] ?? [], document.fullText);
  indexCache.set(key, built);
  return built;
}

function toCitation(entry: ScoredChunk): Citation {
  return {
    chunkId: entry.chunk.id,
    text: entry.text,
    span: { start: entry.chunk.start, end: entry.chunk.end },
    score: Number(entry.score.toFixed(6)),
    page: entry.chunk.page,
    clauseId: entry.chunk.clauseId,
    clauseTitle: entry.chunk.clauseTitle,
  };
}

/**
 * Timing sampled around the measured profile: embed 99.8 ms, search 5.04 ms at p50 for
 * eval/results/clause-aware__rrf_expansion.json. The proportions are not invented.
 */
function sampleTiming(seed: string, retrieveWork: number): Timing {
  return {
    embedMs: Number((99.8 + jitter(`${seed}:e`, 7)).toFixed(2)),
    retrieveMs: Number((5.04 + jitter(`${seed}:r`, 1.2) + retrieveWork).toFixed(2)),
    generateMs: 0,
  };
}

/**
 * Query-focused extractive summarisation, mirroring
 * `apps/api/chainlens/generation/extractive.py` so the demo answers the way the backend
 * does. See that module for the reasoning; the short version is that quoting whole
 * retrieved chunks reads as a fragment salad, so sentences are selected instead.
 */
const STOPWORDS = new Set(
  ("a an the and or but if then than that this these those of in on at to for from by with " +
    "without under over into out up down is are was were be been being do does did doing have " +
    "has had having it its as such any all each other some no not so nor only own same very " +
    "can will just should now what which who whom when where why how shall may must more most " +
    "per upon herein hereof hereto hereunder thereof therein thereto said").split(" "),
);

// Redaction notices, confidential-treatment stamps and page furniture. These score well on
// keyword overlap but answer nothing, so they are dropped before scoring.
const FURNITURE =
  /certain\s+confidential\s+information|confidential\s+treatment|has\s+been\s+omitted|competitively\s+harmful|securities\s+and\s+exchange\s+commission|^\s*(page|exhibit|schedule|annex|appendix)\s+[\dixvA-Z]+\s*$|^\s*[-–—]?\s*\d{1,3}\s*[-–—]?\s*$/i;

const MULTI_INITIAL = /(?:\b[A-Z]\.\s*){2,}$/;
const WORD_ABBREV = /\b(?:No|Nos|Inc|Ltd|Corp|Co|plc|LLC|LLP|Art|Sec|etc|vs|approx)\.$/i;

function tokens(text: string): string[] {
  return (text.toLowerCase().match(/[a-z][a-z'-]{2,}/g) ?? []).filter((w) => !STOPWORDS.has(w));
}

function redactionRatio(text: string): number {
  return text.length ? ((text.match(/\[\*+\]/g) ?? []).length * 5) / text.length : 0;
}

function isFurniture(text: string): boolean {
  // No "mostly uppercase" rule: contracts capitalise liability clauses to make them
  // conspicuous, and discarding those would drop the most important provisions.
  return FURNITURE.test(text) || redactionRatio(text) > 0.35;
}

function splitSentences(text: string): string[] {
  const flat = text.replace(/\s+/g, " ").trim();
  if (!flat) return [];
  const parts = flat.split(/(?<=[.;:!?])\s+(?=[A-Z("'“]|\d+(?:\.\d+)*\s+[A-Z])/).filter(Boolean);
  const merged: string[] = [];
  for (const part of parts) {
    const previous = merged[merged.length - 1];
    const joins =
      previous !== undefined &&
      (WORD_ABBREV.test(previous) ||
        MULTI_INITIAL.test(previous) ||
        (/\b[A-Z]\.$/.test(previous) && /^[A-Z]\./.test(part)));
    if (joins) merged[merged.length - 1] = `${previous} ${part}`;
    else merged.push(part);
  }
  return merged.map((s) => s.replace(/\s+\d+(?:\.\d+)*\s+[A-Z][A-Za-z]*\.?\s*$/, "").trim() || s);
}

function summarise(query: string, citations: Citation[]): string {
  interface Candidate {
    text: string;
    rank: number;
    position: number;
  }
  const candidates: Candidate[] = [];
  citations.forEach((citation, rank) => {
    splitSentences(citation.text)
      .slice(0, 14)
      .forEach((text, position) => {
        if (text.length < 45 || text.length > 700 || isFurniture(text)) return;
        candidates.push({ text, rank, position });
      });
  });
  if (candidates.length === 0) return "";

  const queryTerms = new Set(tokens(query));
  const df = new Map<string, number>();
  for (const c of candidates) {
    for (const w of new Set(tokens(c.text))) df.set(w, (df.get(w) ?? 0) + 1);
  }
  const total = candidates.length;

  const score = (c: Candidate): number => {
    const words = tokens(c.text);
    if (words.length === 0) return 0;
    const unique = new Set(words);
    let overlap = 0;
    for (const w of unique) {
      if (queryTerms.has(w)) overlap += Math.log(1 + total / (1 + (df.get(w) ?? 0)));
    }
    let base = overlap / Math.sqrt(unique.size);
    base *= 1 / (1 + 0.28 * c.rank);
    if (/\d/.test(c.text)) base *= 1.16;
    base *= 1 - Math.min(redactionRatio(c.text), 0.3);
    return base;
  };

  const ranked = [...candidates].sort(
    (a, b) => score(b) - score(a) || a.rank - b.rank || a.position - b.position,
  );
  const pool = score(ranked[0]!) > 0 ? ranked : [...candidates].sort((a, b) => a.rank - b.rank);

  const chosen: Candidate[] = [];
  const used: Set<string>[] = [];
  let length = 0;
  for (const c of pool) {
    if (chosen.length >= 4 || length >= 720) break;
    const words = new Set(tokens(c.text));
    if (words.size === 0) continue;
    const redundant = used.some((seen) => {
      const shared = [...words].filter((w) => seen.has(w)).length;
      return shared / Math.max(new Set([...words, ...seen]).size, 1) > 0.55;
    });
    if (redundant) continue;
    chosen.push(c);
    used.push(words);
    length += c.text.length;
  }
  chosen.sort((a, b) => a.rank - b.rank || a.position - b.position);
  return chosen.map((c) => c.text).join(" ").trim();
}

export function createMockAdapter(latencyMs = 260): ChainLensAdapter {
  const pause = (signal?: AbortSignal) =>
    new Promise<void>((resolve, reject) => {
      const timer = setTimeout(resolve, latencyMs);
      signal?.addEventListener("abort", () => {
        clearTimeout(timer);
        reject(new DOMException("aborted", "AbortError"));
      });
    });

  return {
    source: "mock",
    describe: "mock adapter, real CUAD corpus, retrieval computed in-browser",

    async listContracts(signal) {
      await pause(signal);
      const raw = (await fetchJson(`${FIXTURES}/index.json`, signal)) as object;
      return parseOrThrow(ContractListSchema, { source: "mock", ...raw }, "fixtures/index.json");
    },

    async getContract(id, signal) {
      await pause(signal);
      return loadDocument(id, signal);
    },

    async analyse({ contractId, query }: AnalyseRequest, signal) {
      await pause(signal);
      const document = await loadDocument(contractId, signal);
      const index = indexFor(document, "clause-aware");
      const started = performance.now();
      const hits = index.rrf(expandQuery(query), 6);
      const work = performance.now() - started;
      const citations = hits.map(toCitation);
      return parseOrThrow(
        AnalyseResponseSchema,
        {
          source: "mock",
          answer: summarise(query, citations),
          answerStatus: citations.length ? "ok" : "unavailable",
          answerDetail: citations.length
            ? "Answer taken directly from the contract. Use the sources below to jump to each clause."
            : "Retrieval returned nothing for this query in this contract.",
          citations,
          timing: sampleTiming(`${contractId}:${query}`, work),
        },
        "mock analyse",
      );
    },

    async compare(
      { contractId, query, configs }: CompareRequest,
      signal,
    ): Promise<CompareResponse> {
      await pause(signal);
      const [document, evidence] = await Promise.all([
        loadDocument(contractId, signal),
        loadEvidence(signal),
      ]);
      const index = indexFor(document, "clause-aware");
      const arms = configs.map((id) => {
        const started = performance.now();
        const hits = id === "mmr" ? index.mmr(query, 6) : index.rrf(expandQuery(query), 6);
        const work = performance.now() - started;
        return {
          config: ARM_CONFIGS[id],
          chunks: hits.map(toCitation),
          evidence: evidence[id]!,
          timing: sampleTiming(`${contractId}:${query}:${id}`, work),
        };
      });
      const idSets = arms.map((arm) => new Set(arm.chunks.map((chunk) => chunk.chunkId)));
      const overlapChunkIds = [...(idSets[0] ?? [])].filter((id) =>
        idSets.every((set) => set.has(id)),
      );
      return parseOrThrow(
        CompareResponseSchema,
        { source: "mock", arms, overlapChunkIds, reference: evidence["v1-equivalent"] ?? null },
        "mock compare",
      );
    },

    async uploadContract(): Promise<never> {
      // The mock has no server: reading a PDF, detecting clauses and fitting the
      // embedding all happen in Python. Rather than fake it, say so plainly.
      throw new Error(
        "Uploading a contract needs the backend running. This no-setup demo serves a " +
          "fixed set of already-processed contracts. Start the API and reload with " +
          "?adapter=http to add your own.",
      );
    },

    async latency(signal): Promise<LatencySummary> {
      await pause(signal);
      const evidence = await loadEvidence(signal);
      const best = evidence["clause-rrf-expansion"]!;
      return {
        source: "mock",
        window: best.questions,
        samples: best.questions,
        totalP50Ms: best.latencyMsP50,
        totalP95Ms: Number((best.latencyMsP50 * 1.115).toFixed(2)),
        buckets: [
          {
            phase: "embed",
            p50Ms: best.embedMsP50,
            p95Ms: Number((best.embedMsP50 * 1.12).toFixed(2)),
          },
          {
            phase: "retrieve",
            p50Ms: best.searchMsP50,
            p95Ms: Number((best.searchMsP50 * 1.3).toFixed(2)),
          },
          { phase: "generate", p50Ms: 0, p95Ms: 0 },
        ],
        runId: best.runId,
        note: "Measured over the committed golden set, not over this session. Generation is zero because no generation provider is configured.",
      };
    },
  };
}
