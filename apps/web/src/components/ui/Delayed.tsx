/** Withholds children ~300ms so a fast response never flashes a skeleton. One rule, one place. */
import { useEffect, useState, type ReactNode } from "react";

export function Delayed({ ms = 300, children }: { ms?: number; children: ReactNode }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShow(true), ms);
    return () => clearTimeout(t);
  }, [ms]);
  return show ? <>{children}</> : null;
}
