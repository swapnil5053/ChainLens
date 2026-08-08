/**
 * The wire contract, and the only place a runtime shape is asserted.
 *
 * Every response is parsed with zod at the boundary. Nothing downstream re-validates and
 * nothing downstream defends against a missing field: if it got past this file it has the
 * shape the types claim. That is the point of validating here rather than sprinkling
 * optional chaining through components.
 *
 * The `source` discriminator is deliberate. A mock adapter that cannot be distinguished
 * from a live one is how a demo turns into a false claim, so every payload states which
 * adapter produced it and the interface renders that in the footer.
 */
import { z } from "zod";

export const SourceSchema = z.enum(["mock", "http"]);
export type Source = z.infer<typeof SourceSchema>;

/** Character range into the document's `fullText`. Half-open: [start, end). */
export const SpanSchema = z
  .object({
    start: z.number().int().nonnegative(),
    end: z.number().int().nonnegative(),
  })
  .refine((span) => span.end > span.start, { message: "span end must exceed span start" });
export type Span = z.infer<typeof SpanSchema>;

export const ContractSummarySchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  party: z.string(),
  kind: z.string(),
  pageCount: z.number().int().positive(),
  charCount: z.number().int().positive(),
  clauseCount: z.number().int().nonnegative(),
  chunkCount: z.number().int().nonnegative(),
});
export type ContractSummary = z.infer<typeof ContractSummarySchema>;

export const ContractListSchema = z.object({
  source: SourceSchema,
  contracts: z.array(ContractSummarySchema),
});
export type ContractList = z.infer<typeof ContractListSchema>;

export const UploadResultSchema = z.object({
  source: SourceSchema,
  deduplicated: z.boolean(),
  contract: ContractSummarySchema,
});
export type UploadResult = z.infer<typeof UploadResultSchema>;

export const ChunkRefSchema = z.object({
  id: z.string().min(1),
  ordinal: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  start: z.number().int().nonnegative(),
  end: z.number().int().nonnegative(),
  clauseId: z.string().nullable(),
  clauseTitle: z.string().nullable(),
});
export type ChunkRef = z.infer<typeof ChunkRefSchema>;

export const ContractDocumentSchema = z.object({
  source: SourceSchema,
  id: z.string().min(1),
  title: z.string().min(1),
  pageCount: z.number().int().positive(),
  charCount: z.number().int().positive(),
  fullText: z.string(),
  chunks: z.record(z.string(), z.array(ChunkRefSchema)),
});
export type ContractDocument = z.infer<typeof ContractDocumentSchema>;

export const TimingSchema = z.object({
  embedMs: z.number().nonnegative(),
  retrieveMs: z.number().nonnegative(),
  generateMs: z.number().nonnegative(),
});
export type Timing = z.infer<typeof TimingSchema>;

export const CitationSchema = z.object({
  chunkId: z.string().min(1),
  text: z.string(),
  span: SpanSchema,
  score: z.number(),
  page: z.number().int().positive(),
  clauseId: z.string().nullable(),
  clauseTitle: z.string().nullable(),
});
export type Citation = z.infer<typeof CitationSchema>;

export const AnalyseRequestSchema = z.object({
  contractId: z.string().min(1),
  query: z.string().min(1).max(2000),
});
export type AnalyseRequest = z.infer<typeof AnalyseRequestSchema>;

export const AnalyseResponseSchema = z.object({
  source: SourceSchema,
  answer: z.string(),
  /**
   * `unavailable` is a first-class outcome, not an error. The deployed backend has no
   * generation provider configured, and retrieval plus citations are useful without one;
   * collapsing that into an error would make the interface lie about what failed.
   */
  answerStatus: z.enum(["ok", "unavailable", "error"]),
  answerDetail: z.string().nullable(),
  citations: z.array(CitationSchema),
  timing: TimingSchema,
});
export type AnalyseResponse = z.infer<typeof AnalyseResponseSchema>;

export const ArmConfigSchema = z.object({
  id: z.enum(["mmr", "clause-rrf-expansion"]),
  label: z.string(),
  chunking: z.string(),
  strategy: z.string(),
  expansion: z.boolean(),
});
export type ArmConfig = z.infer<typeof ArmConfigSchema>;

/**
 * Corpus-level evaluation numbers for an arm.
 *
 * These do not describe the query the user just typed. They are aggregates over the
 * committed golden set, and the view is required to say so wherever it renders one.
 */
export const ArmEvidenceSchema = z.object({
  runId: z.string(),
  recallAt6: z.number(),
  mrr: z.number(),
  ndcgAt10: z.number(),
  latencyMsP50: z.number(),
  embedMsP50: z.number(),
  searchMsP50: z.number(),
  questions: z.number().int().positive(),
  datasetSha256: z.string(),
  embeddingProvider: z.string(),
});
export type ArmEvidence = z.infer<typeof ArmEvidenceSchema>;

export const ArmResultSchema = z.object({
  config: ArmConfigSchema,
  chunks: z.array(CitationSchema),
  evidence: ArmEvidenceSchema,
  timing: TimingSchema,
});
export type ArmResult = z.infer<typeof ArmResultSchema>;

export const CompareRequestSchema = z.object({
  contractId: z.string().min(1),
  query: z.string().min(1).max(2000),
  configs: z.array(z.enum(["mmr", "clause-rrf-expansion"])).min(2),
});
export type CompareRequest = z.infer<typeof CompareRequestSchema>;

export const CompareResponseSchema = z.object({
  source: SourceSchema,
  arms: z.array(ArmResultSchema).min(2),
  /** Chunk ids returned by every arm. Computed once so both columns agree. */
  overlapChunkIds: z.array(z.string()),
  reference: ArmEvidenceSchema.nullable(),
});
export type CompareResponse = z.infer<typeof CompareResponseSchema>;

export const LatencyBucketSchema = z.object({
  phase: z.enum(["embed", "retrieve", "generate"]),
  p50Ms: z.number().nonnegative(),
  p95Ms: z.number().nonnegative(),
});
export type LatencyBucket = z.infer<typeof LatencyBucketSchema>;

export const LatencySummarySchema = z.object({
  source: SourceSchema,
  window: z.number().int().nonnegative(),
  samples: z.number().int().nonnegative(),
  totalP50Ms: z.number().nonnegative(),
  totalP95Ms: z.number().nonnegative(),
  buckets: z.array(LatencyBucketSchema),
  runId: z.string().nullable(),
  note: z.string(),
});
export type LatencySummary = z.infer<typeof LatencySummarySchema>;

/** Thrown when a response does not match the contract. Carries the zod issue list. */
export class ContractViolationError extends Error {
  constructor(
    readonly endpoint: string,
    readonly issues: string[],
  ) {
    super(`${endpoint} returned a payload that does not match the contract`);
    this.name = "ContractViolationError";
  }
}

export function parseOrThrow<T>(schema: z.ZodType<T>, value: unknown, endpoint: string): T {
  const result = schema.safeParse(value);
  if (result.success) return result.data;
  throw new ContractViolationError(
    endpoint,
    result.error.issues.map((i) => `${i.path.join(".") || "<root>"}: ${i.message}`),
  );
}
