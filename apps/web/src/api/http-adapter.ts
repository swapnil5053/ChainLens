/**
 * The live adapter.
 *
 * Unexercised: at the time of writing the API is authored but the compose stack has never
 * been executed, and that is recorded in docs/HANDOFF.md rather than glossed over. It is
 * written to the same contract the mock satisfies and validated by the same schemas, so a
 * shape mismatch surfaces as a ContractViolationError naming the endpoint and the field
 * rather than as a blank screen.
 */
import type { ChainLensAdapter } from "./adapter";
import {
  AnalyseResponseSchema,
  CompareResponseSchema,
  ContractDocumentSchema,
  ContractListSchema,
  LatencySummarySchema,
  UploadResultSchema,
  parseOrThrow,
  type AnalyseRequest,
  type CompareRequest,
} from "./contracts";

export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly endpoint: string,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export function createHttpAdapter(baseUrl: string): ChainLensAdapter {
  const request = async (path: string, init: RequestInit, signal?: AbortSignal) => {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: signal ?? null,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new HttpError(
        response.status,
        path,
        detail.slice(0, 300) || `${path} returned ${response.status}`,
      );
    }
    return (await response.json()) as unknown;
  };

  return {
    source: "http",
    describe: `live API at ${baseUrl}`,
    async listContracts(signal) {
      return parseOrThrow(
        ContractListSchema,
        await request("/documents", { method: "GET" }, signal),
        "GET /documents",
      );
    },
    async getContract(id, signal) {
      return parseOrThrow(
        ContractDocumentSchema,
        await request(`/documents/${id}/text`, { method: "GET" }, signal),
        `GET /documents/${id}/text`,
      );
    },
    async analyse(payload: AnalyseRequest, signal) {
      return parseOrThrow(
        AnalyseResponseSchema,
        await request("/analyse", { method: "POST", body: JSON.stringify(payload) }, signal),
        "POST /analyse",
      );
    },
    async compare(payload: CompareRequest, signal) {
      return parseOrThrow(
        CompareResponseSchema,
        await request("/compare", { method: "POST", body: JSON.stringify(payload) }, signal),
        "POST /compare",
      );
    },
    async uploadContract(file: File, signal?: AbortSignal) {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${baseUrl}/documents`, {
        method: "POST",
        body: form,
        signal: signal ?? null,
      });
      if (!response.ok) {
        const detail = await response.text().catch(() => "");
        throw new HttpError(response.status, "/documents", detail.slice(0, 300) || `upload returned ${response.status}`);
      }
      return parseOrThrow(UploadResultSchema, await response.json(), "POST /documents");
    },
    async latency(signal) {
      return parseOrThrow(
        LatencySummarySchema,
        await request("/metrics/latency", { method: "GET" }, signal),
        "GET /metrics/latency",
      );
    },
  };
}
