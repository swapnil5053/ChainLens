/** Adapter selection. Going live is the one line marked below. */
import { resolveMode, type ChainLensAdapter } from "./adapter";
import { createHttpAdapter } from "./http-adapter";
import { createMockAdapter } from "./mock-adapter";

let instance: ChainLensAdapter | null = null;

export function getAdapter(): ChainLensAdapter {
  if (instance) return instance;
  // The one-line swap. `?adapter=http` in the URL, or VITE_ADAPTER=http at build time.
  instance =
    resolveMode() === "http"
      ? createHttpAdapter(import.meta.env.VITE_API_BASE ?? "http://localhost:8000")
      : createMockAdapter();
  return instance;
}

export * from "./adapter";
export * from "./contracts";
