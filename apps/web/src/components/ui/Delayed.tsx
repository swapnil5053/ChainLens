/**
 * Withholds its children for a beat.
 *
 * Skeletons that appear instantly flash on fast responses and read as jank. The guidance
 * is nothing before roughly 300ms; this is that rule, in one place, so no component has to
 * remember it.
 */
import { useEffect, useState, type ReactNode } from "react";

export function Delayed({ ms = 300, children }: { ms?: number; children: ReactNode }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), ms);
    return () => clearTimeout(timer);
  }, [ms]);
  return visible ? <>{children}</> : null;
}
