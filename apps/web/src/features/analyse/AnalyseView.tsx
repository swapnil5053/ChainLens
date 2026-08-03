/**
 * The reader: the contract on the left, the question and its answer on the right.
 *
 * The document takes the primary position and the larger share because it is the thing
 * being read; the ask panel is a sticky sidebar beside it. The header carries the contract
 * picker and upload, so the panes themselves stay free of chrome.
 */
import { useState } from "react";
import { useAnalyse, useContract } from "../../api/queries";
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

  // Switching to a different contract clears the previous question and its answer, so the
  // reader starts fresh rather than seeing an old finding against a new document.
  const handleContractChange = (id: string) => {
    if (id === contractId) return;
    setDraft("");
    onQueryChange("");
    analyse.reset();
    setActiveIndex(null);
    setHoveredIndex(null);
    onContractChange(id);
  };

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
  const asked = analyse.data || analyse.isPending ? query : "";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="relative z-10 flex flex-none flex-wrap items-center justify-between gap-4 border-b border-line px-5 py-3">
        <a
          href="/"
          className="inline-flex items-center gap-2.5 text-[15px] font-extrabold tracking-[0.02em] text-ink transition-colors duration-(--duration) hover:text-accent"
        >
          <svg
            viewBox="0 0 20 20"
            width="15"
            height="15"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="opacity-50"
            aria-hidden="true"
          >
            <path d="M12 4 6 10l6 6" />
          </svg>
          CHAIN<span className="font-light opacity-70">LENS</span>
        </a>
        <div className="flex items-center gap-2.5">
          <ContractSelect selectedId={contractId} onSelect={handleContractChange} />
          <UploadContract onUploaded={handleContractChange} />
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-rows-2 lg:grid-cols-[minmax(0,63fr)_minmax(340px,37fr)] lg:grid-rows-1">
        {/* The contract, dominant */}
        <section className="min-h-0 border-line max-lg:border-b" aria-label="Contract">
          <DocumentPane
            state={documentState}
            citations={citations}
            activeIndex={activeIndex}
            hoveredIndex={hoveredIndex}
            onSelectCitation={setActiveIndex}
          />
        </section>

        {/* The question and its answer */}
        <section
          className="flex min-h-0 flex-col border-line bg-panel lg:border-l"
          aria-label="Answer"
        >
          <form
            className="flex-none px-5 pb-3.5 pt-5"
            onSubmit={(e) => {
              e.preventDefault();
              run(draft);
            }}
          >
            <div className="flex items-end gap-2.5 rounded-lg border border-line-strong bg-panel-raised p-2.5 pl-3.5 transition-colors duration-(--duration) focus-within:border-accent">
              <textarea
                rows={2}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    run(draft);
                  }
                }}
                placeholder={contractId ? "Ask about this agreement" : "Open a contract first"}
                disabled={!contractId}
                aria-label="Question"
                className="max-h-24 flex-1 resize-none border-0 bg-transparent py-1 text-body text-ink outline-none disabled:opacity-60"
              />
              <button
                type="submit"
                aria-label="Send question"
                disabled={!contractId || draft.trim().length === 0 || analyse.isPending}
                className="grid h-[34px] w-[34px] flex-none place-items-center rounded-[10px] bg-accent text-[#06180F] transition-colors duration-(--duration) hover:bg-accent-strong disabled:opacity-40"
              >
                <svg
                  viewBox="0 0 16 16"
                  width="14"
                  height="14"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M8 13V3M3.8 7.2 8 3l4.2 4.2" />
                </svg>
              </button>
            </div>
            <p className="mx-0.5 mt-2 text-[11.5px] text-ink-faint">
              Enter sends &middot; Shift + Enter adds a line
            </p>
          </form>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-7 pt-1.5">
            {asked ? (
              <p className="mb-4 border-l-2 border-accent pl-3 text-body font-medium leading-normal text-ink-muted">
                {asked}
              </p>
            ) : null}
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
    </div>
  );
}
