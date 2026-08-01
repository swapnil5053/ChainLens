/**
 * The query layer. Every server interaction in the application goes through here.
 *
 * Two rules from the frontend-states guidance are implemented once, centrally, rather
 * than per component:
 *   - a refetch never blanks populated content (keepPreviousData)
 *   - a contract violation is never retried, because a payload that fails zod will fail
 *     it again; retrying only delays the error a developer needs to see
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getAdapter } from "./index";
import { ContractViolationError } from "./contracts";
import type { AnalyseRequest, CompareRequest } from "./contracts";

export const queryKeys = {
  contracts: ["contracts"] as const,
  contract: (id: string) => ["contract", id] as const,
  latency: ["latency"] as const,
};

export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ContractViolationError) return false;
  return failureCount < 2;
}

export function useContracts() {
  return useQuery({
    queryKey: queryKeys.contracts,
    queryFn: ({ signal }) => getAdapter().listContracts(signal),
    staleTime: 5 * 60_000,
    retry: shouldRetry,
  });
}

export function useContract(id: string | null) {
  return useQuery({
    queryKey: queryKeys.contract(id ?? "none"),
    queryFn: ({ signal }) => getAdapter().getContract(id!, signal),
    enabled: Boolean(id),
    // Contract text does not change under us, and refetching 130 kB on every focus would
    // be the kind of waste that makes a reader distrust the latency panel.
    staleTime: Infinity,
    placeholderData: keepPreviousData,
    retry: shouldRetry,
  });
}

export function useAnalyse() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (request: AnalyseRequest) => getAdapter().analyse(request),
    // Each answer contributes a latency sample, so the badge refreshes rather than
    // continuing to show a figure that predates the query just watched.
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.latency }),
    retry: shouldRetry,
  });
}

export function useCompare() {
  return useMutation({
    mutationFn: (request: CompareRequest) => getAdapter().compare(request),
    retry: shouldRetry,
  });
}

export function useLatency() {
  return useQuery({
    queryKey: queryKeys.latency,
    queryFn: ({ signal }) => getAdapter().latency(signal),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    retry: shouldRetry,
  });
}
