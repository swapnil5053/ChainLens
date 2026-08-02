/**
 * The whole motion budget: one short opacity+translate on first content. Motion v12 is
 * ~27 kB gzipped, too much for one transition on the critical path, so this is the only
 * importer and it is loaded lazily by its consumer. Duration comes from the token layer,
 * so reduced-motion is already handled here.
 */
import { LazyMotion, domAnimation } from "motion/react";
import * as m from "motion/react-m";
import type { ReactNode } from "react";

function duration(): number {
  if (typeof window === "undefined") return 0.14;
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--duration").trim();
  const n = Number.parseFloat(raw);
  return Number.isNaN(n) ? 0.14 : raw.endsWith("ms") ? n / 1000 : n;
}

export default function EnterOnce({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <LazyMotion features={domAnimation} strict>
      <m.div
        initial={{ opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: duration(), ease: [0.2, 0, 0, 1] }}
        className={className}
      >
        {children}
      </m.div>
    </LazyMotion>
  );
}
