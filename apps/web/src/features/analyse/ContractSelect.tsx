/**
 * Contract selection as one compact control, not a permanent sidebar.
 *
 * "Show only what must be shown": on the Analyse screen the contract you are reading is
 * what matters, not the list of 28 you are not. A native select keeps the full corpus one
 * click away, stays keyboard- and screen-reader-correct for free, and virtualizes itself
 * at the browser level, so nothing here needs TanStack Virtual any more.
 */
import { useContracts } from "../../api/queries";

export function ContractSelect({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const query = useContracts();
  const contracts = query.data?.contracts ?? [];

  if (query.isError) {
    return (
      <button
        type="button"
        onClick={() => void query.refetch()}
        className="text-meta text-flag hover:underline"
      >
        Contracts failed to load. Retry.
      </button>
    );
  }

  return (
    <label className="flex items-center gap-2.5">
      <span className="text-[12px] text-ink-faint max-sm:sr-only">Contract</span>
      <select
        value={selectedId ?? ""}
        disabled={query.isPending}
        onChange={(e) => onSelect(e.target.value)}
        className="min-h-9 min-w-[236px] max-w-[46ch] truncate rounded-[9px] border border-line-strong bg-panel-raised px-3 py-2 text-meta font-medium text-ink disabled:opacity-60"
      >
        <option value="" disabled>
          {query.isPending ? "Loading contracts..." : "Select a contract"}
        </option>
        {contracts.map((c) => (
          <option key={c.id} value={c.id}>
            {c.title} - {c.kind}
          </option>
        ))}
      </select>
    </label>
  );
}
