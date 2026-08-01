/**
 * The single interface every view talks to.
 *
 * Going live is one line in `getAdapter`. No component imports an adapter directly and no
 * component knows which one is in use, beyond rendering the `source` field the payload
 * carries so a demo can never be mistaken for live data.
 */
import type {
  AnalyseRequest,
  AnalyseResponse,
  CompareRequest,
  CompareResponse,
  ContractDocument,
  ContractList,
  LatencySummary,
  Source,
} from "./contracts";

export interface ChainLensAdapter {
  readonly source: Source;
  /** Rendered in the interface footer, so the active data path is never ambiguous. */
  readonly describe: string;
  listContracts(signal?: AbortSignal): Promise<ContractList>;
  getContract(id: string, signal?: AbortSignal): Promise<ContractDocument>;
  analyse(request: AnalyseRequest, signal?: AbortSignal): Promise<AnalyseResponse>;
  compare(request: CompareRequest, signal?: AbortSignal): Promise<CompareResponse>;
  latency(signal?: AbortSignal): Promise<LatencySummary>;
}

export type AdapterMode = "mock" | "http";

export function resolveMode(): AdapterMode {
  const override = new URLSearchParams(window.location.search).get("adapter");
  if (override === "http" || override === "mock") return override;
  return (import.meta.env.VITE_ADAPTER as AdapterMode | undefined) ?? "mock";
}
