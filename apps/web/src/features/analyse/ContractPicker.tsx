/**
 * Contract selection. Virtualized because 29 rows today is 2,900 on a real corpus, and the
 * row geometry is fixed at 52px so the skeleton matches it exactly.
 */
import { useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { ContractSummary } from "../../api/contracts";
import { useContracts } from "../../api/queries";
import { Button } from "../../components/ui/Button";
import { Delayed } from "../../components/ui/Delayed";
import { SkeletonRow } from "../../components/ui/Skeleton";
import { EmptyState, ErrorRegion } from "../../components/ui/StateRegion";

const ROW_HEIGHT = 52;

export function ContractPicker({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [filter, setFilter] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const query = useContracts();

  const all = query.data?.contracts ?? [];
  const needle = filter.trim().toLowerCase();
  const rows: ContractSummary[] = needle
    ? all.filter(
        (contract) =>
          contract.title.toLowerCase().includes(needle) ||
          contract.kind.toLowerCase().includes(needle),
      )
    : all;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  return (
    <section className="field flex min-h-0 flex-col" aria-label="Contracts">
      <div className="flex items-baseline gap-3 border-b border-rule px-3 py-2">
        <h2 className="field-label">Corpus</h2>
        <span className="numeric ml-auto text-micro text-ink-faint">
          {query.isSuccess ? `${rows.length} / ${all.length}` : null}
        </span>
      </div>

      <div className="border-b border-rule px-3 py-2">
        <label className="field-label" htmlFor="contract-filter">
          Filter
        </label>
        <input
          id="contract-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="title or type"
          className="mt-1 w-full rounded-[2px] border border-rule-control bg-ground px-2 py-1 text-small text-ink placeholder:text-ink-faint"
        />
      </div>

      {query.isPending ? (
        <Delayed>
          <div className="flex flex-col" aria-busy="true" aria-label="Loading contracts">
            {Array.from({ length: 8 }, (_, index) => (
              <SkeletonRow key={index} />
            ))}
          </div>
        </Delayed>
      ) : null}

      {query.isError ? (
        <div className="p-3">
          <ErrorRegion
            title="Contract list unavailable"
            error={query.error}
            onRetry={() => void query.refetch()}
            hint="The corpus is served as static fixtures, so this usually means they are missing. Run python scripts/build_web_fixtures.py."
          />
        </div>
      ) : null}

      {query.isSuccess && rows.length === 0 ? (
        <div className="p-3">
          {all.length === 0 ? (
            <EmptyState
              title="No contracts indexed"
              cause="The corpus index loaded but held no contracts. With the shipped fixtures this should not happen; it means the index was generated from an empty corpus directory."
            />
          ) : (
            <EmptyState
              title="Filter matched nothing"
              cause={`No contract title or type contains "${filter.trim()}". The corpus holds ${all.length} supply-chain agreements.`}
              action={<Button onClick={() => setFilter("")}>Clear filter</Button>}
            />
          )}
        </div>
      ) : null}

      {query.isSuccess && rows.length > 0 ? (
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
          <ul
            className="relative m-0 w-full list-none p-0"
            style={{ height: `${virtualizer.getTotalSize()}px` }}
          >
            {virtualizer.getVirtualItems().map((item) => {
              const contract = rows[item.index]!;
              const active = contract.id === selectedId;
              return (
                <li
                  key={contract.id}
                  className="absolute left-0 top-0 w-full"
                  style={{ height: `${item.size}px`, transform: `translateY(${item.start}px)` }}
                >
                  <button
                    type="button"
                    onClick={() => onSelect(contract.id)}
                    aria-current={active ? "true" : undefined}
                    className={
                      "flex h-full w-full items-center gap-3 border-b border-rule px-3 text-left " +
                      "transition-colors duration-(--duration-hover) ease-(--ease-enter) " +
                      (active
                        ? "bg-panel-raised shadow-[inset_2px_0_0_0_var(--accent)]"
                        : "hover:bg-panel-raised")
                    }
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-small text-ink">{contract.title}</span>
                      <span className="numeric block text-micro text-ink-faint">
                        {contract.kind} - {contract.pageCount}pp - {contract.clauseCount} clauses
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
