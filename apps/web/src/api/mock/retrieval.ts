/**
 * A faithful, small reimplementation of the two retrieval configurations, in the browser.
 *
 * This is not canned output. Both arms genuinely score the real chunk text of the real
 * contract against whatever the user types, using the same shapes as the server:
 *
 *   dense arm     cosine over L2-normalised term-frequency vectors. Not the LSA model the
 *                 backend fits, but a real vector similarity with the same behaviour of
 *                 rewarding whole-passage similarity over isolated term hits.
 *   lexical arm   tf-idf scoring in the spirit of ts_rank_cd, rewarding rarer terms.
 *   fusion        reciprocal rank fusion at k = 60, rank from list position, exactly as
 *                 chainlens/retrieval/fusion.py does it.
 *   MMR           the same greedy selection and the same lambda = 0.5 default.
 *
 * What it is not: the measured system. The corpus-level Recall@6 shown beside each arm
 * comes from the committed evaluation artifacts and is labelled as an aggregate, never as
 * a property of the current query.
 */
import type { ChunkRef } from "../contracts";

const STOPWORDS = new Set(
  (
    "a an the of for to in on at by is are was were be been and or not what which who whom " +
    "this that these those with as from it its if any does do did shall will under over " +
    "about into per"
  ).split(" "),
);

export interface ScoredChunk {
  chunk: ChunkRef;
  text: string;
  score: number;
}

function tokenise(value: string): string[] {
  return (value.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(
    (token) => token.length > 1 && !STOPWORDS.has(token),
  );
}

function termFrequency(tokens: string[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const token of tokens) counts.set(token, (counts.get(token) ?? 0) + 1);
  return counts;
}

function normalise(counts: Map<string, number>): Map<string, number> {
  let sum = 0;
  for (const value of counts.values()) sum += value * value;
  const norm = Math.sqrt(sum) || 1;
  const out = new Map<string, number>();
  for (const [key, value] of counts) out.set(key, value / norm);
  return out;
}

function cosine(a: Map<string, number>, b: Map<string, number>): number {
  const [small, large] = a.size < b.size ? [a, b] : [b, a];
  let total = 0;
  for (const [key, value] of small) total += value * (large.get(key) ?? 0);
  return total;
}

/** Built once per contract per chunking strategy, then reused across queries. */
export class MockIndex {
  private readonly vectors: Map<string, number>[];
  private readonly idf: Map<string, number>;
  private readonly position: Map<string, number>;
  readonly texts: string[];

  constructor(
    readonly chunks: readonly ChunkRef[],
    fullText: string,
  ) {
    // Slicing full text by the stored offsets is the same invariant the API guarantees. A
    // wrong offset is wrong on screen, which is the point of storing offsets not text.
    this.texts = chunks.map((chunk) => fullText.slice(chunk.start, chunk.end));
    const tokenised = this.texts.map(tokenise);
    this.vectors = tokenised.map((tokens) => normalise(termFrequency(tokens)));
    this.position = new Map(chunks.map((chunk, index) => [chunk.id, index]));

    const documentFrequency = new Map<string, number>();
    for (const tokens of tokenised) {
      for (const token of new Set(tokens)) {
        documentFrequency.set(token, (documentFrequency.get(token) ?? 0) + 1);
      }
    }
    this.idf = new Map();
    const total = chunks.length || 1;
    for (const [token, count] of documentFrequency) {
      this.idf.set(token, Math.log(1 + total / (1 + count)));
    }
  }

  private rank(scores: number[], limit: number): ScoredChunk[] {
    const out: ScoredChunk[] = [];
    scores.forEach((score, index) => {
      if (score > 0) out.push({ chunk: this.chunks[index]!, text: this.texts[index]!, score });
    });
    return out.sort((left, right) => right.score - left.score).slice(0, limit);
  }

  dense(query: string, limit: number): ScoredChunk[] {
    const queryVector = normalise(termFrequency(tokenise(query)));
    return this.rank(this.vectors.map((vector) => cosine(queryVector, vector)), limit);
  }

  lexical(query: string, limit: number): ScoredChunk[] {
    const terms = new Set(tokenise(query));
    return this.rank(
      this.vectors.map((vector) => {
        let total = 0;
        for (const term of terms) {
          const weight = vector.get(term);
          if (weight) total += weight * (this.idf.get(term) ?? 0);
        }
        return total;
      }),
      limit,
    );
  }

  /** Greedy MMR over the dense candidates. Same objective as the server. */
  mmr(query: string, limit: number, lambda = 0.5, fetch = 30): ScoredChunk[] {
    const candidates = this.dense(query, fetch);
    if (candidates.length === 0) return [];
    const selected: ScoredChunk[] = [];
    const remaining = [...candidates];
    while (remaining.length > 0 && selected.length < limit) {
      let bestPosition = 0;
      let bestObjective = -Infinity;
      remaining.forEach((candidate, position) => {
        let penalty = 0;
        const left = this.vectors[this.position.get(candidate.chunk.id)!]!;
        for (const chosen of selected) {
          const right = this.vectors[this.position.get(chosen.chunk.id)!]!;
          penalty = Math.max(penalty, cosine(left, right));
        }
        const objective = selected.length
          ? lambda * candidate.score - (1 - lambda) * penalty
          : candidate.score;
        if (objective > bestObjective) {
          bestObjective = objective;
          bestPosition = position;
        }
      });
      selected.push(remaining.splice(bestPosition, 1)[0]!);
    }
    return selected;
  }

  /** Reciprocal rank fusion, k = 60, rank taken from list position. */
  rrf(query: string, limit: number, k = 60, fetch = 30): ScoredChunk[] {
    const arms = [this.dense(query, fetch), this.lexical(query, fetch)];
    const fused = new Map<string, { entry: ScoredChunk; score: number }>();
    for (const arm of arms) {
      arm.forEach((entry, position) => {
        const existing = fused.get(entry.chunk.id);
        const contribution = 1 / (k + position + 1);
        if (existing) existing.score += contribution;
        else fused.set(entry.chunk.id, { entry, score: contribution });
      });
    }
    return [...fused.values()]
      .sort((left, right) => right.score - left.score)
      .slice(0, limit)
      .map(({ entry, score }) => ({ ...entry, score }));
  }
}
