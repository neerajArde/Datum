// components/ResultsTable.tsx
// The table of extracted values, the filter buttons above it, and the evidence card
// for whichever row is selected.

// "use client" = this component runs in the browser, because it has state (useState)
// and reacts to clicks. Everything it imports (FilterButtons, StatusBadge, EvidenceCard) runs there too.
"use client";

import { useState } from "react";
import type { Row } from "@/lib/types";
import FilterButtons, { type Filter } from "./FilterButtons";
import StatusBadge from "./StatusBadge";
import EvidenceCard from "./EvidenceCard";

export default function ResultsTable({ rows }: { rows: Row[] }) {
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
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Material</th>
                  <th className="px-4 py-3 font-medium">Property</th>
                  <th className="px-4 py-3 font-medium">Value</th>
                  <th className="px-4 py-3 font-medium">Unit</th>
                  <th className="px-4 py-3 font-medium">Page</th>
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
                      <td className="px-4 py-3">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="px-4 py-3 text-zinc-900">{row.material}</td>
                      <td className="px-4 py-3 text-zinc-600">{row.property}</td>
                      <td className="px-4 py-3 font-mono text-zinc-900">
                        {row.value}
                        {row.error !== "" && <span className="text-zinc-500"> ± {row.error}</span>}
                      </td>
                      <td className="px-4 py-3 text-zinc-600">{row.unit}</td>
                      <td className="px-4 py-3 text-zinc-600">p. {row.page}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* the card gets the selected row as a PROP; it doesn't know about clicks or filters */}
        <div className="lg:sticky lg:top-6">
          <EvidenceCard row={selected} />
        </div>
      </div>
    </section>
  );
}
