/**
 * The latency finding, stated plainly: the vector search is not the expensive part. The
 * query embedding is almost all of it. One headline number, one bar, one small table.
 */
import { useLatency } from "../../api/queries";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonText } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";
import { ms, percent } from "../../lib/format";

const FILL: Record<string, string> = {
  embed: "bg-accent",
  retrieve: "bg-line-strong",
  generate: "bg-line",
};

export function LatencyView() {
  const latency = useLatency();

  if (latency.isError)
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        <ErrorRegion message="The latency summary could not be loaded." onRetry={() => void latency.refetch()} />
      </div>
    );
  if (latency.isPending)
    return (
      <div className="mx-auto max-w-3xl px-6 py-8" aria-busy>
        <Delayed>
          <SkeletonText lines={5} />
        </Delayed>
      </div>
    );

  const d = latency.data;
  if (!d || d.samples === 0)
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        <EmptyState
          title="No queries measured yet"
          cause="Latency is aggregated from answered questions. Ask something on the Analyse screen and it fills in here."
        />
      </div>
    );

  const embed = d.buckets.find((b) => b.phase === "embed");
  const retrieve = d.buckets.find((b) => b.phase === "retrieve");

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 overflow-y-auto px-6 py-8">
      <div>
        <p className="eyebrow">Where the time goes, p50</p>
        <p className="num mt-1 text-display font-semibold text-ink">
          {percent(embed?.p50Ms ?? 0, d.totalP50Ms)}%
        </p>
        <p className="mt-1 max-w-[68ch] text-meta text-ink-muted">
          of a {ms(d.totalP50Ms)} ms query is spent embedding the question. Postgres does both
          searches and the fusion in {ms(retrieve?.p50Ms ?? 0)} ms. A latency budget belongs on
          caching query embeddings, not on tuning the index.
        </p>
      </div>

      <div className="flex h-7 overflow-hidden rounded-sm" role="img" aria-label={d.buckets.map((b) => `${b.phase} ${ms(b.p50Ms)} ms`).join(", ")}>
        {d.buckets.map((b) => {
          const w = percent(b.p50Ms, d.totalP50Ms);
          return w > 0 ? <div key={b.phase} className={FILL[b.phase]} style={{ width: `${w}%` }} /> : null;
        })}
      </div>

      <table className="w-full text-body">
        <caption className="sr-only">Latency by phase, p50 and p95, milliseconds</caption>
        <thead>
          <tr className="border-b border-line text-meta text-ink-faint">
            <th scope="col" className="py-2 text-left font-medium">phase</th>
            <th scope="col" className="py-2 text-right font-medium">p50 ms</th>
            <th scope="col" className="py-2 text-right font-medium">p95 ms</th>
            <th scope="col" className="py-2 text-right font-medium">share</th>
          </tr>
        </thead>
        <tbody>
          {d.buckets.map((b) => (
            <tr key={b.phase} className="border-b border-line">
              <th scope="row" className="py-2 text-left font-normal text-ink">{b.phase}</th>
              <td className="num py-2 text-right text-ink">{ms(b.p50Ms)}</td>
              <td className="num py-2 text-right text-ink">{ms(b.p95Ms)}</td>
              <td className="num py-2 text-right text-ink-muted">{percent(b.p50Ms, d.totalP50Ms)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-meta text-ink-faint">{d.note}</p>
    </div>
  );
}
