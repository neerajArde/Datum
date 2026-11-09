// components/ResultsTable.tsx
// The table of extracted values, the filter buttons above it, and the evidence panel
// for whichever row is selected (where you can also accept / edit / reject it).

// "use client" = this component runs in the browser, because it has state (useState)
// and reacts to clicks. Everything it imports (FilterButtons, StatusBadge, EvidencePanel) runs there too.
"use client";

import { useState } from "react";
import type { Row } from "@/lib/types";
import type { Decision, Decisions } from "@/lib/review";
import FilterButtons, { type Filter } from "./FilterButtons";
import StatusBadge from "./StatusBadge";
import EvidencePanel from "./EvidencePanel";

type Props = {
  rows: Row[];
  decisions?: Decisions; //                                optional: what's been accepted / edited / rejected
  onDecide?: (id: string, decision: Decision) => void; //   optional: lets the panel record decisions
};

export default function ResultsTable({ rows, decisions = {}, onDecide }: Props) {
  // STATE 1: which filter is selected. Starts at "all".
  const [filter, setFilter] = useState<Filter>("all");

  // STATE 2: which row is selected. We store only its id (not a copy of the row),
  // so there's one source of truth: the rows list.
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Everything below is recomputed from rows + state on every redraw,
  // so the counts, the heading, the table and the card can never disagree.
  const counts: Record<Filter, number> = {
    all: rows.length,
    verified: rows.filter((row) => row.status === "verified").length,
    review: rows.filter((row) => row.status === "review").length,
    flagged: rows.filter((row) => row.status === "flagged").length,
  };
  const shown = filter === "all" ? rows : rows.filter((row) => row.status === filter);

  // the selected row, but only if the current filter still shows it
  const selected = shown.find((row) => row.id === selectedId) ?? null;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-zinc-900">
          {shown.length} {shown.length === 1 ? "value" : "values"}
        </h2>
        {/* props down: what's selected + the counts. Event up: onPick calls our setFilter */}
        <FilterButtons selected={filter} counts={counts} onPick={setFilter} />
      </div>

      {/* two columns on wide screens: table on the left, evidence card on the right */}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        {shown.length === 0 ? (
          <p className="rounded-xl border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500">
            No {filter} values in this run.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
            <table className="w-full whitespace-nowrap text-left text-sm">
              <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-3 py-3 font-medium">Material</th>
                  <th className="px-3 py-3 font-medium">Property</th>
                  <th className="px-3 py-3 font-medium">Value</th>
                  <th className="px-3 py-3 font-medium">Page</th>
                  <th className="px-3 py-3 font-medium">Decision</th>
                </tr>
              </thead>
              <tbody>
                {/* one <tr> per row. key={row.id} lets React tell rows apart when the list changes */}
                {shown.map((row) => {
                  const isSelected = row.id === selectedId;
                  return (
                    <tr
                      key={row.id}
                      // clicking a row (or pressing Enter on it) selects it
                      onClick={() => setSelectedId(row.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") setSelectedId(row.id);
                      }}
                      tabIndex={0}
                      aria-selected={isSelected}
                      className={`cursor-pointer border-t border-zinc-100 outline-none focus-visible:bg-zinc-100 ${
                        isSelected ? "bg-yellow-50" : "hover:bg-zinc-50"
                      }`}
                    >
                      <td className="px-3 py-3">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="px-3 py-3 text-zinc-900">{row.material}</td>
                      <td className="px-3 py-3 text-zinc-600">{row.property}</td>
                      <td className="px-3 py-3 text-zinc-900">
                        <span className="font-mono">{row.value}</span>
                        {row.error !== "" && <span className="font-mono text-zinc-600"> ± {row.error}</span>}
                        <span className="ml-1.5 text-xs text-zinc-500">{row.unit}</span>
                      </td>
                      <td className="px-3 py-3 text-zinc-600">p. {row.page}</td>
                      <td className="px-3 py-3 text-zinc-600">{describe(row, decisions[row.id])}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* the panel gets the selected row as a PROP; it doesn't know about clicks or filters.
            key = new row -> fresh panel, so its edit box and "more notes" start closed */}
        <div className="lg:sticky lg:top-6">
          <EvidencePanel
            key={selected?.id ?? "none"}
            row={selected}
            decision={selected !== null ? decisions[selected.id] : undefined}
            onDecide={onDecide !== undefined && selected !== null ? (decision) => onDecide(selected.id, decision) : undefined}
          />
        </div>
      </div>
    </section>
  );
}

// a short label for the Decision column
function describe(row: Row, decision: Decisions[string] | undefined): string {
  if (decision === undefined) return row.status === "verified" ? "✓ auto" : "—";
  if (decision.kind === "accepted") return "✓ accepted";
  if (decision.kind === "rejected") return "✕ rejected";
  return `✎ ${decision.value}`;
}
