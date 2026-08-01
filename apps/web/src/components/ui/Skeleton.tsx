/**
 * Geometry-matched skeletons.
 *
 * These take the shape of the thing that is loading rather than being generic grey
 * rectangles, which is the difference between a placeholder and a promise. There is no
 * shimmer: a static tinted block at the right size says the same thing without animating
 * a surface the user is about to read.
 */
export function SkeletonLine({ width = "100%" }: { width?: string }) {
  return (
    <span aria-hidden="true" className="block h-[0.8em] rounded-[1px] bg-panel-raised" style={{ width }} />
  );
}

export function SkeletonParagraph({ lines = 4 }: { lines?: number }) {
  const widths = ["100%", "97%", "99%", "88%", "94%", "72%"];
  return (
    <div aria-hidden="true" className="flex flex-col gap-[0.55em]">
      {Array.from({ length: lines }, (_, index) => (
        <SkeletonLine key={index} width={widths[index % widths.length]} />
      ))}
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div aria-hidden="true" className="flex h-[52px] items-center gap-3 border-b border-rule px-3">
      <SkeletonLine width="42%" />
      <span className="ml-auto" />
      <SkeletonLine width="3rem" />
    </div>
  );
}
