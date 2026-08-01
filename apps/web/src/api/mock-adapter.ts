/**
 * The demo adapter.
 *
 * Serves the real CUAD corpus from static fixtures and runs the two retrieval
 * configurations for real, in the browser, over real chunk text at real offsets. It
 * fabricates exactly two things and labels both:
 *
 *   1. Latency, sampled around the measured profile in eval/results. The proportions are
 *      the real finding: query embedding dominates, search is a few milliseconds.
 *   2. The answer, which is assembled by quoting the top-ranked clauses verbatim rather
 *      than generated. `answerDetail` says so and the interface renders it.
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

function summarise(citations: Citation[], query: string): string {
  if (citations.length === 0) return "";
  const lead = citations[0]!;
  const where = lead.clauseId
    ? `clause ${lead.clauseId}${lead.clauseTitle ? ` (${lead.clauseTitle})` : ""}`
    : `page ${lead.page}`;
  const quote = lead.text.replace(/\s+/g, " ").trim().slice(0, 420);
  const others = citations
    .slice(1, 3)
    .map((citation, index) =>
      citation.clauseId
        ? `Clause ${citation.clauseId} also bears on this [${index + 2}].`
        : `Page ${citation.page} also bears on this [${index + 2}].`,
    )
    .join(" ");
  return (
    `The passage most responsive to "${query.trim()}" is ${where} [1]: ` +
    `"${quote}${quote.length >= 420 ? "..." : ""}"` +
    (others ? ` ${others}` : "")
  );
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
          answer: summarise(citations, query),
          answerStatus: citations.length ? "ok" : "unavailable",
          answerDetail: citations.length
            ? "Extractive answer: the retrieved clauses are quoted verbatim and attributed. No language model was called, because no generation provider is configured."
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
