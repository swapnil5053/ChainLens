/** Geometry-matched skeletons: the shape of what loads, not a generic block. No shimmer. */
export function SkeletonLine({ width = "100%" }: { width?: string }) {
  return <span aria-hidden className="block h-[0.7em] rounded-sm bg-panel-raised" style={{ width }} />;
}

export function SkeletonText({ lines = 4 }: { lines?: number }) {
  const widths = ["100%", "96%", "98%", "84%", "92%", "70%"];
  return (
    <div aria-hidden className="flex flex-col gap-[0.6em]">
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonLine key={i} width={widths[i % widths.length]} />
      ))}
    </div>
  );
}
