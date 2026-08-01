/**
 * View 3. The latency finding, made legible.
 *
 * The finding this screen exists to state: the vector search is not the expensive part.
 * Postgres serves both retrieval arms in single-digit milliseconds while the query
 * embedding takes almost all of the budget. That is the opposite of the usual intuition,
 * so it gets the largest elements on the screen rather than a column in a table.
 */
import { useLatency } from "../../api/queries";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonParagraph } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";
import { ms, percent } from "../../lib/format";
import { StackedBar } from "./StackedBar";

export function LatencyView() {
  const latency = useLatency();

  if (latency.isError) {
    return (
      <div className="p-4">
        <ErrorRegion
          title="Latency summary unavailable"
          error={latency.error}
          onRetry={() => void latency.refetch()}
          hint="Retrieval itself is unaffected; this panel reads an aggregate endpoint."
        />
      </div>
    );
  }

  if (latency.isPending) {
    return (
      <div className="p-4" aria-busy="true">
        <Delayed>
          <div className="field p-4">
            {/* Reserves the final height so the bar does not shift in when it arrives. */}
            <div className="h-8 w-full rounded-[2px] border border-rule bg-panel-raised" />
            <div className="mt-4">
              <SkeletonParagraph lines={4} />
            </div>
          </div>
        </Delayed>
      </div>
    );
  }

  const data = latency.data;
  if (!data || data.samples === 0) {
    return (
      <div className="p-4">
        <EmptyState
          title="No latency samples yet"
          cause="Latency is aggregated from answered questions. Ask something on the Analyse view and this fills in."
        />
      </div>
    );
  }

  const embed = data.buckets.find((bucket) => bucket.phase === "embed");
  const retrieve = data.buckets.find((bucket) => bucket.phase === "retrieve");

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-4">
      <section className="field p-4" aria-label="Latency breakdown">
        <div className="flex flex-wrap items-baseline gap-x-8 gap-y-3">
          <div>
            <p className="field-label">Total p50</p>
            <p className="numeric text-figure text-ink">{ms(data.totalP50Ms)} ms</p>
          </div>
          <div>
            <p className="field-label">Query embedding share</p>
            <p className="numeric text-figure text-accent">
              {percent(embed?.p50Ms ?? 0, data.totalP50Ms)}%
            </p>
          </div>
          <div>
            <p className="field-label">Postgres search p50</p>
            <p className="numeric text-figure text-ink">{ms(retrieve?.p50Ms ?? 0)} ms</p>
          </div>
          <div>
            <p className="field-label">Total p95</p>
            <p className="numeric text-figure text-ink">{ms(data.totalP95Ms)} ms</p>
          </div>
        </div>

        <div className="mt-5">
          <StackedBar buckets={data.buckets} total={data.totalP50Ms} />
        </div>

        <p className="mt-5 max-w-[76ch] text-small leading-[1.55] text-ink-muted">
          The dense search, the lexical search and the fusion together account for{" "}
          <span className="numeric text-ink">{ms(retrieve?.p50Ms ?? 0)} ms</span>. The query
          embedding accounts for{" "}
          <span className="numeric text-ink">{ms(embed?.p50Ms ?? 0)} ms</span>. A latency budget
          spent on index tuning would be spent in the wrong place; caching or batching query
          embeddings is where the time is.
        </p>
      </section>

      <section className="field p-4" aria-label="Per phase">
        <p className="field-label">Per phase</p>
        <table className="mt-3 w-full border-collapse text-small">
          <caption className="sr-only">Latency by phase, p50 and p95, in milliseconds</caption>
          <thead>
            <tr>
              <th scope="col" className="field-label border-b-2 border-ink py-2 text-left">
                phase
              </th>
              <th scope="col" className="field-label border-b-2 border-ink py-2 text-right">
                p50 ms
              </th>
              <th scope="col" className="field-label border-b-2 border-ink py-2 text-right">
                p95 ms
              </th>
              <th scope="col" className="field-label border-b-2 border-ink py-2 text-right">
                share of p50
              </th>
            </tr>
          </thead>
          <tbody>
            {data.buckets.map((bucket) => (
              <tr key={bucket.phase} className="border-b border-rule">
                <th scope="row" className="py-2 text-left font-normal text-ink">
                  {bucket.phase}
                </th>
                <td className="numeric py-2 text-right text-ink">{ms(bucket.p50Ms)}</td>
                <td className="numeric py-2 text-right text-ink">{ms(bucket.p95Ms)}</td>
                <td className="numeric py-2 text-right text-ink-muted">
                  {percent(bucket.p50Ms, data.totalP50Ms)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 max-w-[76ch] text-micro text-ink-muted">
          {data.note} Source run <span className="numeric">{data.runId ?? "unknown"}</span>,{" "}
          {data.samples} samples.
        </p>
      </section>
    </div>
  );
}
