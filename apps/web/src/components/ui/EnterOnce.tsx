/**
 * The application's entire motion budget: one 180ms enter, transform and opacity only.
 *
 * Motion v12 costs roughly 27 kB gzipped, which is a poor trade against one transition if
 * it sits on the critical path. This module is the only importer of the library and it is
 * loaded lazily by its consumer, so the cost is paid after the first answer resolves,
 * behind a network call the user is already waiting on, rather than before the first paint
 * of a screen that has not animated anything yet.
 *
 * The duration is read from the token layer, so prefers-reduced-motion is already handled
 * and this component does not check it.
 */
import { LazyMotion, domAnimation } from "motion/react";
import * as m from "motion/react-m";
import type { ReactNode } from "react";

function readDuration(): number {
  if (typeof window === "undefined") return 0.18;
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--duration-enter").trim();
  const parsed = Number.parseFloat(raw);
  if (Number.isNaN(parsed)) return 0.18;
  return raw.endsWith("ms") ? parsed / 1000 : parsed;
}

export default function EnterOnce({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <LazyMotion features={domAnimation} strict>
      <m.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: readDuration(), ease: [0.2, 0, 0, 1] }}
        className={className}
      >
        {children}
      </m.div>
    </LazyMotion>
  );
}
