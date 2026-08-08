/**
 * URL-held state: which view, which contract, what was asked.
 *
 * These three are in the URL rather than in a store because a finding should be
 * shareable. A colleague opening the link lands on the same clause of the same contract
 * with the same question in the box.
 */
import { useCallback, useEffect, useState } from "react";

export type ViewId = "analyse" | "compare" | "latency";

export interface AppState {
  view: ViewId;
  contractId: string | null;
  query: string;
}

function read(): AppState {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  return {
    view: view === "compare" || view === "latency" ? view : "analyse",
    contractId: params.get("contract"),
    query: params.get("q") ?? "",
  };
}

export function useAppState(): [AppState, (patch: Partial<AppState>) => void] {
  const [state, setState] = useState<AppState>(read);

  useEffect(() => {
    const onPop = () => setState(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // useCallback here is identity stability for a history writer passed to children, not
  // memoisation for performance; the React Compiler handles the latter.
  const update = useCallback((patch: Partial<AppState>) => {
    setState((previous) => {
      const next = { ...previous, ...patch };
      const params = new URLSearchParams(window.location.search);
      params.set("view", next.view);
      if (next.contractId) params.set("contract", next.contractId);
      else params.delete("contract");
      if (next.query) params.set("q", next.query);
      else params.delete("q");
      window.history.replaceState(null, "", `?${params.toString()}`);
      return next;
    });
  }, []);

  return [state, update];
}
