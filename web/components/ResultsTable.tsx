// components/ResultsTable.tsx
// The table of extracted values, with the filter buttons above it.

// "use client" = this component runs in the browser, because it has state (useState)
// and reacts to clicks. Everything it imports (FilterButtons, StatusBadge) runs there too.
"use client";

import { useState } from "react";
import type { Row } from "@/lib/types";
import FilterButtons, { type Filter } from "./FilterButtons";
import StatusBadge from "./StatusBadge";

export default function ResultsTable({ rows }: { rows: Row[] }) {
  // STATE: which filter is selected. Starts at "all".
  // Calling setFilter(...) is the ONLY way to change it, and it makes React redraw this component.
  const [filter, setFilter] = useState<Filter>("all");

  // Everything below is recomputed from `rows` and `filter` on every redraw,
  // so the counts, the heading and the table can never disagree.
  const counts: Record<Filter, number> = {
    all: rows.length,
    verified: rows.filter((row) => row.status === "verified").length,
    review: rows.filter((row) => row.status === "review").length,
    flagged: rows.filter((row) => row.status === "flagged").length,
  };
  const shown = filter === "all" ? rows : rows.filter((row) => row.status === filter);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-zinc-900">
          {shown.length} {shown.length === 1 ? "value" : "values"}
        </h2>
        {/* props down: what's selected + the counts. Event up: onPick calls our setFilter */}
        <FilterButtons selected={filter} counts={counts} onPick={setFilter} />
      </div>

      {shown.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500">
          No {filter} values in this run.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
          <table className="w-full text-left text-sm">
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
              {shown.map((row) => (
                <tr key={row.id} className="border-t border-zinc-100 hover:bg-zinc-50">
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
