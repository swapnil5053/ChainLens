/**
 * One stacked bar, one accent, no chart library.
 *
 * A three-segment horizontal bar does not need a charting dependency, and pulling one in
 * would put its default palette and its default tooltip into a screen whose whole point is
 * that the proportions are legible at a glance.
 */
import type { LatencyBucket } from "../../api/contracts";
import { ms, percent } from "../../lib/format";

const FILL: Record<LatencyBucket["phase"], string> = {
  embed: "bg-accent",
  retrieve: "bg-ink-muted",
  generate: "bg-rule-control",
};

export function StackedBar({ buckets, total }: { buckets: readonly LatencyBucket[]; total: number }) {
  return (
    <div>
      <div
        className="flex h-8 w-full overflow-hidden rounded-[2px] border border-rule-control"
        role="img"
        aria-label={buckets
          .map((bucket) => `${bucket.phase} ${ms(bucket.p50Ms)} milliseconds`)
          .join(", ")}
      >
        {buckets.map((bucket) => {
          const share = percent(bucket.p50Ms, total);
          if (share === 0) return null;
          return (
            <div
              key={bucket.phase}
              className={`${FILL[bucket.phase]} h-full`}
              style={{ width: `${share}%` }}
              title={`${bucket.phase}: ${ms(bucket.p50Ms)} ms, ${share}%`}
            />
          );
        })}
      </div>
      <ul className="m-0 mt-2 flex list-none flex-wrap gap-x-5 gap-y-1 p-0">
        {buckets.map((bucket) => (
          <li key={bucket.phase} className="flex items-center gap-2">
            <span className={`${FILL[bucket.phase]} inline-block h-2 w-2 rounded-[1px]`} />
            <span className="text-micro text-ink-muted">{bucket.phase}</span>
            <span className="numeric text-micro text-ink">
              {ms(bucket.p50Ms)} ms - {percent(bucket.p50Ms, total)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
