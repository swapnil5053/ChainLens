/**
 * View 1. Document-forward split: the contract dominates, the finding sits beside it.
 *
 * State placement, decided in the taste pass before this file existed:
 *   server   contract list, contract text, analysis result  -> TanStack Query
 *   URL      selected contract, query text                  -> shareable
 *   local    active and hovered citation                    -> ephemeral
 */
import { useState } from "react";
import { useAnalyse, useContract } from "../../api/queries";
import { Button } from "../../components/ui/Button";
import { AnswerRecord, type AnswerState } from "./AnswerRecord";
import { ContractPicker } from "./ContractPicker";
import { DocumentPane, type DocumentPaneState } from "./DocumentPane";

export function AnalyseView({
  contractId,
  query,
  onContractChange,
  onQueryChange,
}: {
  contractId: string | null;
  query: string;
  onContractChange: (id: string) => void;
  onQueryChange: (value: string) => void;
}) {
  const [draft, setDraft] = useState(query);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const contract = useContract(contractId);
  const analyse = useAnalyse();

  const run = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed || !contractId) return;
    setDraft(trimmed);
    onQueryChange(trimmed);
    setActiveIndex(null);
    analyse.mutate(
      { contractId, query: trimmed },
      { onSuccess: (result) => setActiveIndex(result.citations.length ? 0 : null) },
    );
  };

  const documentState: DocumentPaneState = !contractId
    ? { status: "idle" }
    : contract.isPending
      ? { status: "loading" }
      : contract.isError
        ? { status: "error", error: contract.error, onRetry: () => void contract.refetch() }
        : { status: "ready", document: contract.data };

  const answerState: AnswerState = analyse.isPending
    ? { status: "loading" }
    : analyse.isError
      ? { status: "error", error: analyse.error, onRetry: () => run(draft) }
      : analyse.data
        ? { status: "ready", result: analyse.data }
        : { status: "idle", contractTitle: contract.data?.title ?? null };

  const citations = analyse.data?.citations ?? [];
  const canAsk = Boolean(contractId) && draft.trim().length > 0;

  return (
    <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[minmax(0,62fr)_minmax(0,38fr)]">
      {/* Document first in the DOM on wide screens, second on narrow: the finding is what a
          phone user needs first, the document is what a desk user reads. */}
      <div className="order-2 flex min-h-0 flex-col lg:order-1">
        <DocumentPane
          state={documentState}
          citations={citations}
          activeIndex={activeIndex}
          hoveredIndex={hoveredIndex}
          onSelectCitation={setActiveIndex}
        />
      </div>

      <div className="order-1 flex min-h-0 flex-col gap-4 overflow-y-auto lg:order-2">
        <form
          className="field shrink-0 p-4"
          onSubmit={(event) => {
            event.preventDefault();
            run(draft);
          }}
        >
          <label className="field-label" htmlFor="analyse-query">
            Question
          </label>
          <textarea
            id="analyse-query"
            rows={2}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                run(draft);
              }
            }}
            placeholder="What is the cap on liability?"
            className="mt-1 w-full resize-none rounded-[2px] border border-rule-control bg-ground px-2 py-1.5 text-small text-ink placeholder:text-ink-faint"
          />
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              variant="primary"
              disabled={!canAsk || analyse.isPending}
              disabledReason={
                !contractId
                  ? "Open a contract first: retrieval is scoped to one agreement."
                  : draft.trim().length === 0
                    ? "Type a question."
                    : "Retrieval in progress."
              }
            >
              {analyse.isPending ? "Retrieving" : "Ask"}
            </Button>
            {!contractId ? (
              <span className="text-micro text-ink-muted">
                Open a contract first: retrieval is scoped to one agreement.
              </span>
            ) : null}
          </div>
        </form>

        <div className="shrink-0">
          <AnswerRecord
            state={answerState}
            activeIndex={activeIndex}
            hoveredIndex={hoveredIndex}
            onActivate={setActiveIndex}
            onHover={setHoveredIndex}
            onExample={(example) => {
              setDraft(example);
              run(example);
            }}
          />
        </div>

        <div className="flex min-h-64 flex-1 flex-col">
          <ContractPicker selectedId={contractId} onSelect={onContractChange} />
        </div>
      </div>
    </div>
  );
}
