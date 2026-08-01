/**
 * View 2. The same query through two retrieval configurations, side by side.
 *
 * The point of this screen is that the evaluation becomes visible. Two things with
 * different epistemic status appear here and the view is required to keep them apart:
 *
 *   per-query chunks    computed now, from this query, against this contract
 *   Recall@6 and MRR    corpus aggregates over 110 lawyer-annotated questions, read from
 *                       the committed artifacts, true of the configuration rather than of
 *                       this query
 *
 * That distinction is carried in the markup, not left to the reader to infer.
 */
import { useState } from "react";
import type { ArmResult, Citation, CompareResponse } from "../../api/contracts";
import { useCompare } from "../../api/queries";
import { Button } from "../../components/ui/Button";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonParagraph } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";
import { clauseLabel, oneLine } from "../../lib/format";

export function CompareView({ contractId, query }: { contractId: string | null; query: string }) {
  const [draft, setDraft] = useState(query);
  const compare = useCompare();

  const run = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed || !contractId) return;
    compare.mutate({ contractId, query: trimmed, configs: ["mmr", "clause-rrf-expansion"] });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <form
        className="field shrink-0 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          run(draft);
        }}
      >
        <label className="field-label" htmlFor="compare-query">
          Question, run through both configurations
        </label>
        <div className="mt-1 flex flex-wrap gap-2">
          <input
            id="compare-query"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="What is the cap on liability?"
            className="min-w-0 flex-1 rounded-[2px] border border-rule-control bg-ground px-2 py-1.5 text-small text-ink placeholder:text-ink-faint"
          />
          <Button
            type="submit"
            variant="primary"
            disabled={!contractId || draft.trim().length === 0 || compare.isPending}
            disabledReason={
              !contractId
                ? "Open a contract on the Analyse view first."
                : "Type a question to compare."
            }
          >
            {compare.isPending ? "Running both" : "Compare"}
          </Button>
        </div>
        {!contractId ? (
          <p className="mt-2 text-micro text-ink-muted">
            Open a contract on the Analyse view first. Both arms search the same agreement,
            which is what makes the comparison fair.
          </p>
        ) : null}
      </form>

      {compare.isError ? (
        <ErrorRegion
          title="Comparison failed"
          error={compare.error}
          onRetry={() => run(draft)}
          hint="Your question is preserved. The Analyse view is unaffected."
        />
      ) : null}

      {compare.isPending ? (
        <Delayed>
          <div className="grid gap-4 md:grid-cols-2" aria-busy="true">
            {["MMR baseline", "RRF fusion + expansion"].map((label) => (
              <div key={label} className="field p-4">
                <p className="field-label">{label}</p>
                <div className="mt-3">
                  <SkeletonParagraph lines={7} />
                </div>
              </div>
            ))}
          </div>
        </Delayed>
      ) : null}

      {!compare.isPending && !compare.data && !compare.isError ? (
        <EmptyState
          title="No comparison run yet"
          cause="Ask the same question of both configurations. The left arm is the retrieval strategy this project shipped first; the right arm is what replaced it, and the grid figures beside each say by how much."
        />
      ) : null}

      {compare.data ? <Arms response={compare.data} /> : null}
    </div>
  );
}

function Arms({ response }: { response: CompareResponse }) {
  const overlap = new Set(response.overlapChunkIds);
  const [left, right] = response.arms;
  const delta = left && right ? right.evidence.recallAt6 - left.evidence.recallAt6 : null;

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="field flex flex-wrap items-baseline gap-x-6 gap-y-2 p-4">
        <div>
          <p className="field-label">Recall@6 delta, corpus</p>
          <p className="numeric text-figure text-accent">
            {delta === null ? "--" : `${delta > 0 ? "+" : ""}${delta.toFixed(3)}`}
          </p>
        </div>
        <p className="max-w-[64ch] text-micro leading-[1.5] text-ink-muted">
          Measured over {left?.evidence.questions ?? 0} lawyer-annotated questions in the
          committed golden set, <strong className="text-ink">not over the query above</strong>.
          Runs <span className="numeric">{left?.evidence.runId}</span> and{" "}
          <span className="numeric">{right?.evidence.runId}</span>, embedding provider{" "}
          <span className="numeric">{left?.evidence.embeddingProvider}</span>.
          {response.reference ? (
            <>
              {" "}
              The configuration this project originally shipped combined MMR with recursive
              chunking and scored{" "}
              <span className="numeric">{response.reference.recallAt6.toFixed(3)}</span>, worse
              still.
            </>
          ) : null}
        </p>
        <span className="numeric ml-auto rounded-[3px] border border-rule-control px-2 py-1 text-micro text-ink-muted">
          {overlap.size} of {left?.chunks.length ?? 0} chunks shared
        </span>
      </div>

      <div className="grid min-h-0 gap-4 md:grid-cols-2">
        {response.arms.map((arm) => (
          <ArmColumn key={arm.config.id} arm={arm} overlap={overlap} />
        ))}
      </div>
    </div>
  );
}

function ArmColumn({ arm, overlap }: { arm: ArmResult; overlap: ReadonlySet<string> }) {
  return (
    <section className="field flex min-h-0 flex-col" aria-label={arm.config.label}>
      <header className="border-b border-rule px-4 py-3">
        <div className="flex items-baseline gap-3">
          <h3 className="field-label">{arm.config.label}</h3>
          <span className="numeric ml-auto text-micro text-ink-faint">
            R@6 {arm.evidence.recallAt6.toFixed(3)}
          </span>
        </div>
        <p className="numeric mt-1 text-micro text-ink-muted">
          {arm.config.chunking} - {arm.config.strategy}
          {arm.config.expansion ? " - glossary expansion" : ""}
        </p>
      </header>

      {arm.chunks.length === 0 ? (
        <div className="p-4">
          <EmptyState
            title="This arm returned nothing"
            cause="No chunk scored above zero under this configuration. The other column may still have results, which is itself the comparison."
          />
        </div>
      ) : (
        <ol className="m-0 flex min-h-0 list-none flex-col overflow-y-auto p-0">
          {arm.chunks.map((chunk, index) => (
            <ChunkRow
              key={chunk.chunkId}
              index={index}
              chunk={chunk}
              shared={overlap.has(chunk.chunkId)}
            />
          ))}
        </ol>
      )}
    </section>
  );
}

function ChunkRow({ index, chunk, shared }: { index: number; chunk: Citation; shared: boolean }) {
  return (
    <li
      className={
        "border-b border-rule px-4 py-3 transition-colors duration-(--duration-hover) " +
        "ease-(--ease-enter) hover:bg-panel-raised " +
        (shared ? "" : "shadow-[inset_2px_0_0_0_var(--accent)]")
      }
    >
      <div className="flex items-baseline gap-2">
        <span className="numeric text-micro text-ink-faint">{index + 1}</span>
        <span className="numeric text-micro text-ink">{clauseLabel(chunk.clauseId, chunk.page)}</span>
        <span
          className="numeric ml-auto text-micro text-ink-faint"
          title={shared ? "returned by both arms" : "returned by this arm only"}
        >
          {shared ? "shared" : "unique"}
        </span>
      </div>
      {chunk.clauseTitle ? <p className="mt-1 text-small text-ink">{chunk.clauseTitle}</p> : null}
      <p className="mt-1 text-small leading-[1.5] text-ink-muted">{oneLine(chunk.text, 220)}</p>
    </li>
  );
}
