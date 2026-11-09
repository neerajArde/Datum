// components/Composer.tsx
// The first thing a researcher sees: which properties to extract, which papers to read, and Extract.
// It only collects the inputs. What happens on Extract is the parent's job (onExtract),
// so when the backend arrives, only the parent changes.

"use client";

import { useRef, useState } from "react";
import { addPapers, formatSize, type Paper } from "@/lib/papers";
import Button from "./ui/Button";
import Card from "./ui/Card";

type Props = {
  onExtract: (input: { properties: string; papers: Paper[] }) => void;
};

export default function Composer({ onExtract }: Props) {
  // STATE: what the researcher typed, the papers they added, drag-over highlight, and skip messages
  const [properties, setProperties] = useState("");
  const [papers, setPapers] = useState<Paper[]>([]);
  const [dragging, setDragging] = useState(false);
  const [skipped, setSkipped] = useState<string[]>([]);

  // a REF points at a real page element. Here: the hidden file picker, so our own button can open it.
  const picker = useRef<HTMLInputElement>(null);

  function add(files: FileList | null) {
    if (files === null) return;
    const result = addPapers(papers, Array.from(files));
    setPapers(result.papers);
    setSkipped(result.skipped);
  }

  const ready = papers.length > 0;
  const extractAll = properties.trim() === "";

  return (
    <Card as="section" className="space-y-5 p-6">
      {/* 1. what to extract */}
      <div className="space-y-1.5">
        <label htmlFor="properties" className="text-sm font-medium text-ink">
          Properties
        </label>
        <input
          id="properties"
          value={properties}
          onChange={(event) => setProperties(event.target.value)}
          placeholder="e.g. μC*, volumetric capacitance C*, electrical conductivity"
          className="w-full rounded-md border border-line bg-subtle px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-line-strong focus:bg-surface focus:outline-none"
        />
        <p className="text-xs text-soft">Separate with commas. Leave empty to extract every property the papers report.</p>
      </div>

      {/* 2. which papers */}
      <div className="space-y-2">
        <p className="text-sm font-medium text-ink">Papers</p>

        {papers.length > 0 && (
          <ul className="space-y-1.5">
            {papers.map((paper) => (
              <li key={paper.id} className="flex items-center gap-3 rounded-md border border-line bg-subtle px-3 py-2 text-sm">
                <span className="min-w-0 flex-1 truncate text-ink">{paper.file.name}</span>
                <span className="shrink-0 text-xs text-soft">{formatSize(paper.file.size)}</span>
                <button
                  type="button"
                  onClick={() => setPapers(papers.filter((p) => p.id !== paper.id))}
                  aria-label={`Remove ${paper.file.name}`}
                  className="shrink-0 rounded px-1.5 text-soft hover:bg-subtle-strong hover:text-ink"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* the drop zone: drag PDFs onto it, or click the button to pick them */}
        <div
          onDragOver={(event) => {
            event.preventDefault(); // without this, the browser opens the PDF instead of letting us drop it
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            add(event.dataTransfer.files);
          }}
          className={`flex flex-wrap items-center gap-3 rounded-lg border border-dashed px-4 py-4 transition-colors ${
            dragging ? "border-ink bg-highlight-soft" : "border-line-strong bg-subtle"
          }`}
        >
          <Button variant="secondary" onClick={() => picker.current?.click()}>
            Choose PDFs
          </Button>
          <span className="text-sm text-soft">or drop them here · PDF, up to 50 MB each</span>
          <input
            ref={picker}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            hidden
            onChange={(event) => {
              add(event.target.files);
              event.target.value = ""; // so choosing the same file again still counts as a change
            }}
          />
        </div>

        {/* aria-live: screen readers announce these messages when they appear */}
        <div aria-live="polite">
          {skipped.length > 0 && <p className="text-sm text-review-ink">Skipped: {skipped.join(" · ")}</p>}
        </div>
      </div>

      {/* 3. go */}
      <div className="flex items-center justify-end gap-3">
        {!ready && <span className="text-sm text-faint">Add at least one paper</span>}
        <Button size="lg" disabled={!ready} onClick={() => onExtract({ properties: properties.trim(), papers })}>
          {extractAll ? "Extract all" : "Extract"}
        </Button>
      </div>
    </Card>
  );
}
