// components/EvidencePanel.tsx
// THE one view of a value, used everywhere:
//   - compact: beside the table, for scanning (no `review` prop)
//   - focus:   in review mode, one value at a time, with the queue and keyboard shortcuts
// Same order in both: answer first (value + verdict), proof second (quote + page), then decide.

"use client";

import { useEffect, useState } from "react";
import type { Row } from "@/lib/types";
import { notesFor, verdictFor, type Decision, type Level } from "@/lib/review";
import { splitAtValue } from "@/lib/highlight";
import StatusBadge from "./StatusBadge";
import Button from "./ui/Button";
import Card from "./ui/Card";

// Only passed in review mode. Its presence is what switches the panel to "focus".
export type ReviewNav = {
  position: number; // 1-based place in the queue
  total: number;
  onNext: () => void;
  onPrevious: () => void;
  onExit: () => void;
};

type Props = {
  row: Row | null;
  decision?: Decision;
  onDecide?: (decision: Decision) => void; // leave out to show the panel read-only
  review?: ReviewNav;
};

const VERDICT_STYLE = {
  good: "border-verified-line bg-verified-bg text-verified-ink",
  careful: "border-review-line bg-review-bg text-review-ink",
  stop: "border-flagged-line bg-flagged-bg text-flagged-ink",
};
const VERDICT_ICON = { good: "✅", careful: "⚠️", stop: "⛔" };
const LEVEL_DOT: Record<Level, string> = { blocker: "bg-flagged", caution: "bg-review", info: "bg-line-strong" };

export default function EvidencePanel({ row, decision, onDecide, review }: Props) {
  const focus = review !== undefined;

  // STATE: are we typing a corrected value, and are the extra notes open?
  // (The parent gives this component a new `key` per row, so these reset for each value.)
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(row?.value ?? "");
  const [showAll, setShowAll] = useState(false);
  // beside the table, verified rows hide their buttons until "Report a problem" is clicked
  const [reporting, setReporting] = useState(false);

  // Keyboard shortcuts, ONLY in review mode (so a stray key in the table never rejects a value).
  // useEffect = "do this outside of drawing": listen for keys while the panel is on screen,
  // and stop listening when it goes away (the function we return).
  useEffect(() => {
    if (review === undefined || row === null || onDecide === undefined) return;
    const value = row.value;
    const nav = review;
    const decide = onDecide;
    function onKey(event: KeyboardEvent) {
      if (editing) return; // while typing a correction, letters are just letters
      const key = event.key.toLowerCase();
      if (key === "j") nav.onNext();
      else if (key === "k") nav.onPrevious();
      else if (key === "a") decide({ kind: "accepted" });
      else if (key === "r") decide({ kind: "rejected" });
      else if (key === "e") {
        event.preventDefault(); // don't type "e" into the box we're about to open
        setDraft(value);
        setEditing(true);
      } else if (key === "escape") nav.onExit();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editing, row, onDecide, review]);

  // nothing selected yet (table view): a gentle hint instead of an empty box
  if (row === null) {
    return (
      <aside className="rounded-xl border border-dashed border-line-strong p-6 text-sm text-soft">
        Select a row to see where its value came from.
      </aside>
    );
  }

  const notes = notesFor(row);
  const verdict = verdictFor(row, notes);
  const extraNotes = notes.slice(1); // the first note is already in the verdict
  const parts = splitAtValue(row.evidence, row.value);

  // Verified rows are accepted automatically, so beside the table they show no buttons,
  // just a quiet "Report a problem". In review mode (e.g. a spot-check) buttons always show.
  const quiet = !focus && row.status === "verified" && !reporting && decision === undefined;

  function startEdit() {
    setDraft(row?.value ?? "");
    setEditing(true);
  }
  function saveEdit() {
    const value = draft.trim();
    if (onDecide !== undefined && value !== "" && value !== row?.value) onDecide({ kind: "edited", value });
    setEditing(false);
  }

  return (
    <Card as="aside" className={`space-y-4 ${focus ? "p-6" : "p-5"}`}>
      {/* review mode only: back link and place in the queue */}
      {review !== undefined && (
        <div className="flex items-center justify-between text-sm text-soft">
          <Button variant="ghost" onClick={review.onExit} size="inline">
            ← Back to table
          </Button>
          <span>
            {review.position} of {review.total} · <kbd className="font-mono">K</kbd> ↑ <kbd className="font-mono">J</kbd> ↓
          </span>
        </div>
      )}

      {/* 1. the answer: what was found */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-soft">
            {row.material} · {row.property}
          </p>
          <p className={`font-semibold tracking-tight text-ink ${focus ? "text-3xl" : "text-2xl"}`}>
            {decision?.kind === "edited" ? (
              <>
                <span className="text-faint line-through">{row.value}</span> {decision.value}
              </>
            ) : (
              row.value
            )}
            {row.error !== "" && <span className="text-muted"> ± {row.error}</span>}
            <span className="ml-2 text-base font-normal text-soft">{row.unit}</span>
          </p>
        </div>
        <StatusBadge status={row.status} />
      </div>

      {/* 2. the verdict: one sentence answering "can I use this number?" */}
      <p className={`rounded-lg border px-4 py-3 text-sm ${VERDICT_STYLE[verdict.tone]}`}>
        {VERDICT_ICON[verdict.tone]} {verdict.text}
      </p>

      {extraNotes.length > 0 && (
        <div className="text-sm text-muted">
          <button type="button" onClick={() => setShowAll(!showAll)} className="text-soft hover:text-ink">
            {showAll ? "▾" : "▸"} {extraNotes.length} more {extraNotes.length === 1 ? "note" : "notes"}
          </button>
          {showAll && (
            <ul className="mt-2 space-y-1.5">
              {extraNotes.map((note) => (
                <li key={note.text} className="flex items-start gap-2">
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${LEVEL_DOT[note.level]}`} />
                  {note.text}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* 3. the proof: for now the quote in a page-style box; the real PDF page comes with the backend */}
      <div className="rounded-lg border border-line bg-subtle p-1">
        <p className="px-3 pt-2 text-xs text-soft">
          Page {row.page} of {row.paper}
          {row.origin === "cited" && row.reference !== "" && <> · from reference [{row.reference}]</>}
        </p>
        <blockquote
          className={`m-2 rounded bg-surface p-4 font-serif leading-relaxed text-body shadow-sm ${
            focus ? "text-base" : "text-sm"
          }`}
        >
          {parts === null ? (
            row.evidence
          ) : (
            <>
              {parts[0]}
              <mark className="rounded bg-highlight px-0.5 text-ink">{parts[1]}</mark>
              {parts[2]}
            </>
          )}
        </blockquote>
      </div>

      {/* 4. decide */}
      {onDecide !== undefined && quiet && (
        <Button variant="ghost" onClick={() => setReporting(true)} size="inline" className="font-normal">
          ⋯ Report a problem with this value
        </Button>
      )}
      {onDecide !== undefined &&
        !quiet &&
        (editing ? (
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault(); // stay on the page instead of the browser's default form submit
              saveEdit();
            }}
          >
            <input
              autoFocus
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") setEditing(false);
              }}
              aria-label="Corrected value"
              className="min-w-0 flex-1 rounded-md border border-line-strong px-3 py-2 font-mono text-sm"
            />
            <Button type="submit" size="lg">
              Save
            </Button>
          </form>
        ) : (
          <div className="flex flex-wrap gap-2">
            <ActionButton label="Accept" shortcut={focus ? "A" : undefined} active={decision?.kind === "accepted"} onClick={() => onDecide({ kind: "accepted" })} />
            <ActionButton label="Edit" shortcut={focus ? "E" : undefined} active={decision?.kind === "edited"} onClick={startEdit} />
            <ActionButton label="Reject" shortcut={focus ? "R" : undefined} active={decision?.kind === "rejected"} onClick={() => onDecide({ kind: "rejected" })} />
          </div>
        ))}

      <p className="text-xs text-faint">Extracted by {row.provider}</p>
    </Card>
  );
}

// shortcut hints are shown only in review mode, where the shortcuts actually work
function ActionButton(props: { label: string; shortcut?: string; onClick: () => void; active: boolean }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium ${
        props.active ? "border-ink bg-ink text-white" : "border-line-strong text-body hover:bg-subtle"
      }`}
    >
      {props.shortcut !== undefined && (
        <kbd className={`rounded px-1.5 font-mono text-xs ${props.active ? "bg-surface/20" : "bg-subtle-strong"}`}>{props.shortcut}</kbd>
      )}
      {props.label}
    </button>
  );
}
