/**
 * The same query through two retrieval configurations, side by side. Simplified: the
 * corpus Recall@6 delta stated once at the top, then two lean lists of what each arm
 * returned, with shared vs unique marked in text. The evaluation numbers are corpus
 * aggregates from the committed artifacts and are labelled as such, not as properties of
 * this query.
 */
import { useState } from "react";
import type { ArmResult, Citation, CompareResponse } from "../../api/contracts";
import { useCompare } from "../../api/queries";
import { Button } from "../../components/ui/Button";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonText } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";
import { clauseLabel, oneLine } from "../../lib/format";

export function CompareView({ contractId, query }: { contractId: string | null; query: string }) {
  const [draft, setDraft] = useState(query);
  const compare = useCompare();
  const run = (v: string) => {
    const q = v.trim();
    if (q && contractId) compare.mutate({ contractId, query: q, configs: ["mmr", "clause-rrf-expansion"] });
  };

  return (
    <div className="mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col gap-6 overflow-y-auto px-6 py-6">
      <form
        className="flex items-start gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          run(draft);
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={contractId ? "Ask both configurations the same thing..." : "Open a contract on Analyse first"}
          disabled={!contractId}
          aria-label="Question"
          className="min-h-9 flex-1 rounded-sm border border-line-strong bg-ground px-3 text-body text-ink placeholder:text-ink-faint disabled:opacity-60"
        />
        <Button
          type="submit"
          variant="primary"
          disabled={!contractId || draft.trim().length === 0 || compare.isPending}
          disabledReason={!contractId ? "Open a contract first." : "Type a question."}
        >
          {compare.isPending ? "Running" : "Compare"}
        </Button>
      </form>

      {compare.isError ? (
        <ErrorRegion message="The comparison failed." onRetry={() => run(draft)} />
      ) : null}

      {compare.isPending ? (
        <Delayed>
          <div className="grid gap-8 md:grid-cols-2" aria-busy>
            <SkeletonText lines={7} />
            <SkeletonText lines={7} />
          </div>
        </Delayed>
      ) : null}

      {!compare.isPending && !compare.data && !compare.isError ? (
        <EmptyState
          title="Compare two retrieval strategies"
          cause="The left is the strategy this project first shipped; the right is what replaced it. Ask the same question and see both what they return now and how they score across the whole test set."
        />
      ) : null}

      {compare.data ? <Result data={compare.data} /> : null}
    </div>
  );
}

function Result({ data }: { data: CompareResponse }) {
  const overlap = new Set(data.overlapChunkIds);
  const [left, right] = data.arms;
  const delta = left && right ? right.evidence.recallAt6 - left.evidence.recallAt6 : null;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Recall@6 across the test set</p>
        <p className="num mt-1 text-display font-semibold text-accent">
          {delta === null ? "--" : `+${delta.toFixed(3)}`}
        </p>
        <p className="mt-1 max-w-[70ch] text-meta text-ink-muted">
          Measured over {left?.evidence.questions ?? 0} lawyer-annotated questions, not the query
          above. {right?.config.label} scores {right?.evidence.recallAt6.toFixed(3)} against{" "}
          {left?.evidence.recallAt6.toFixed(3)} for {left?.config.label}.
          {data.reference
            ? ` The original default scored ${data.reference.recallAt6.toFixed(3)}, lower still.`
            : ""}
        </p>
      </div>

      <div className="grid gap-8 md:grid-cols-2">
        {data.arms.map((arm) => (
          <Arm key={arm.config.id} arm={arm} overlap={overlap} />
        ))}
      </div>
    </div>
  );
}

function Arm({ arm, overlap }: { arm: ArmResult; overlap: ReadonlySet<string> }) {
  return (
    <section aria-label={arm.config.label}>
      <div className="flex items-baseline justify-between border-b border-line pb-2">
        <h3 className="text-body font-semibold text-ink">{arm.config.label}</h3>
        <span className="num text-meta text-ink-faint">R@6 {arm.evidence.recallAt6.toFixed(3)}</span>
      </div>
      {arm.chunks.length === 0 ? (
        <p className="mt-3 text-meta text-ink-muted">This configuration returned nothing.</p>
      ) : (
        <ol className="mt-1">
          {arm.chunks.map((c, i) => (
            <Row key={c.chunkId} index={i} chunk={c} shared={overlap.has(c.chunkId)} />
          ))}
        </ol>
      )}
    </section>
  );
}

function Row({ index, chunk, shared }: { index: number; chunk: Citation; shared: boolean }) {
  return (
    <li className="border-b border-line py-3">
      <div className="flex items-baseline gap-2">
        <span className="num text-meta text-ink-faint">{index + 1}</span>
        <span className="num text-meta text-ink">{clauseLabel(chunk.clauseId, chunk.page)}</span>
        <span className={`ml-auto text-meta ${shared ? "text-ink-faint" : "text-accent"}`}>
          {shared ? "shared" : "unique"}
        </span>
      </div>
      <p className="mt-1 text-meta leading-[1.6] text-ink-muted">{oneLine(chunk.text, 200)}</p>
    </li>
  );
}
