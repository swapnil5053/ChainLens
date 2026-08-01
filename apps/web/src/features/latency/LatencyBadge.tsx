/**
 * The live badge in the masthead: total p50 plus the same stacked proportions, small.
 *
 * Refetching never blanks it: a stale figure with a quiet opacity hint beats an empty box,
 * because the number is the reason the badge exists.
 */
import { useLatency } from "../../api/queries";
import { ms, percent } from "../../lib/format";

export function LatencyBadge({ onOpen }: { onOpen: () => void }) {
  const latency = useLatency();
  const data = latency.data;

  if (latency.isError) {
    return (
      <button
        type="button"
        onClick={() => void latency.refetch()}
        className="numeric min-h-8 rounded-[3px] border border-flag px-2 text-micro text-flag"
      >
        latency unavailable, retry
      </button>
    );
  }

  const embed = data?.buckets.find((bucket) => bucket.phase === "embed");
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={
        data
          ? `Latency p50 ${ms(data.totalP50Ms)} milliseconds, of which query embedding is ${percent(embed?.p50Ms ?? 0, data.totalP50Ms)} percent. Open the latency view.`
          : "Latency, loading. Open the latency view."
      }
      className={
        "flex min-h-8 items-center gap-2 rounded-[3px] border border-rule-control px-2 " +
        "transition-colors duration-(--duration-hover) ease-(--ease-enter) hover:bg-panel-raised " +
        (latency.isFetching ? "opacity-80" : "")
      }
    >
      <span className="field-label">p50</span>
      <span className="numeric text-small text-ink">{data ? `${ms(data.totalP50Ms)} ms` : "--"}</span>
      <span className="flex h-3 w-16 overflow-hidden rounded-[1px] border border-rule">
        {data?.buckets.map((bucket) => {
          const share = percent(bucket.p50Ms, data.totalP50Ms);
          if (share === 0) return null;
          return (
            <span
              key={bucket.phase}
              className={
                bucket.phase === "embed"
                  ? "bg-accent"
                  : bucket.phase === "retrieve"
                    ? "bg-ink-muted"
                    : "bg-rule-control"
              }
              style={{ width: `${share}%` }}
            />
          );
        })}
      </span>
    </button>
  );
}
