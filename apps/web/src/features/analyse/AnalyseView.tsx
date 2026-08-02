/**
 * The primary screen, stripped to what matters: the contract, and the answer beside it.
 *
 * A resizable split with the document dominant. The contract selector and the question
 * box sit in a thin bar above each pane; there is no sidebar, no metadata strip, no
 * badges. The working engine underneath (queries, adapter, marks) is unchanged.
 */
import { useState } from "react";
import { useAnalyse, useContract } from "../../api/queries";
import { Button } from "../../components/ui/Button";
import { AnswerBlock, type AnswerState } from "./AnswerBlock";
import { ContractSelect } from "./ContractSelect";
import { UploadContract } from "./UploadContract";
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
  onQueryChange: (v: string) => void;
}) {
  const [draft, setDraft] = useState(query);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const contract = useContract(contractId);
  const analyse = useAnalyse();

  const run = (value: string) => {
    const q = value.trim();
    if (!q || !contractId) return;
    setDraft(q);
    onQueryChange(q);
    setActiveIndex(null);
    analyse.mutate(
      { contractId, query: q },
      { onSuccess: (r) => setActiveIndex(r.citations.length ? 0 : null) },
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

  return (
    <div className="grid min-h-0 flex-1 grid-rows-2 lg:grid-cols-[3fr_2fr] lg:grid-rows-1">
      {/* Document, dominant */}
      <section className="flex min-h-0 flex-col border-line max-lg:border-b lg:border-r" aria-label="Contract">
        <div className="flex items-center gap-3 border-b border-line px-6 py-3">
          <ContractSelect selectedId={contractId} onSelect={onContractChange} />
          <div className="ml-auto">
            <UploadContract onUploaded={onContractChange} />
          </div>
        </div>
        <div className="min-h-0 flex-1">
          <DocumentPane
            state={documentState}
            citations={citations}
            activeIndex={activeIndex}
            hoveredIndex={hoveredIndex}
            onSelectCitation={setActiveIndex}
          />
        </div>
      </section>

      {/* Answer */}
      <section className="flex min-h-0 flex-col" aria-label="Answer">
        <form
          className="border-b border-line px-6 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            run(draft);
          }}
        >
          <div className="flex items-start gap-2">
            <textarea
              rows={1}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  run(draft);
                }
              }}
              placeholder={contractId ? "Ask about this contract..." : "Open a contract first"}
              disabled={!contractId}
              aria-label="Question"
              className="min-h-9 flex-1 resize-none rounded-sm border border-line-strong bg-ground px-3 py-2 text-body text-ink placeholder:text-ink-faint disabled:opacity-60"
            />
            <Button
              type="submit"
              variant="primary"
              disabled={!contractId || draft.trim().length === 0 || analyse.isPending}
              disabledReason={!contractId ? "Open a contract first." : "Type a question."}
            >
              {analyse.isPending ? "Reading" : "Ask"}
            </Button>
          </div>
        </form>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <AnswerBlock
            state={answerState}
            activeIndex={activeIndex}
            hoveredIndex={hoveredIndex}
            onActivate={setActiveIndex}
            onHover={setHoveredIndex}
            onExample={(q) => {
              setDraft(q);
              run(q);
            }}
          />
        </div>
      </section>
    </div>
  );
}
