/**
 * Add-a-contract control. A quiet "Add PDF" button next to the selector.
 *
 * Only meaningful against the live backend: uploading runs the real parse, clause-detect,
 * hash and embed path server-side. On the mock the adapter has no upload method, so the
 * button is hidden rather than shown-and-broken. On success the new contract is selected
 * and the list refreshes so it appears in the dropdown.
 */
import { useRef, useState } from "react";
import { getAdapter } from "../../api";
import { queryKeys } from "../../api/queries";
import { useQueryClient } from "@tanstack/react-query";

export function UploadContract({ onUploaded }: { onUploaded: (id: string) => void }) {
  const adapter = getAdapter();
  const inputRef = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The mock adapter has no uploadContract; hide the control entirely rather than offer a
  // button that only produces an error.
  if (typeof adapter.uploadContract !== "function") return null;

  const pick = () => inputRef.current?.click();

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const result = await adapter.uploadContract!(file);
      await client.invalidateQueries({ queryKey: queryKeys.contracts });
      onUploaded(result.contract.id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Upload failed.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void upload(file);
        }}
      />
      <button
        type="button"
        onClick={pick}
        disabled={busy}
        className="inline-flex min-h-9 items-center gap-2 rounded-[9px] bg-accent px-3.5 text-meta font-bold text-[#06180F] transition-colors duration-(--duration) hover:bg-accent-strong disabled:opacity-60"
      >
        <svg
          viewBox="0 0 16 16"
          width="13"
          height="13"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M8 12.5V3.5M4.5 7 8 3.5 11.5 7" />
        </svg>
        {busy ? "Adding" : "Upload PDF"}
      </button>
      {error ? (
        <span role="alert" className="max-w-[40ch] text-meta text-flag">
          {error}
        </span>
      ) : null}
    </div>
  );
}
