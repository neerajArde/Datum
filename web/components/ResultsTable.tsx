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
import Card from "./ui/Card";

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
        <h2 className="text-lg font-semibold text-ink">
          {shown.length} {shown.length === 1 ? "value" : "values"}
        </h2>
        {/* props down: what's selected + the counts. Event up: onPick calls our setFilter */}
        <FilterButtons selected={filter} counts={counts} onPick={setFilter} />
      </div>

      {/* two columns on wide screens: table on the left, evidence card on the right */}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        {shown.length === 0 ? (
          <p className="rounded-xl border border-dashed border-line-strong p-8 text-center text-sm text-soft">
            No {filter} values in this run.
          </p>
        ) : (
          <Card className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-left text-sm">
              <thead className="bg-subtle text-xs uppercase tracking-wide text-soft">
                <tr>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-3 py-3 font-medium">Material</th>
                  <th className="px-3 py-3 font-medium">Property</th>
                  <th className="px-3 py-3 font-medium">Value</th>
                  <th className="px-3 py-3 font-medium">Page</th>
                </tr>
              </thead>
              <tbody>
                {/* one <tr> per row. key={row.id} lets React tell rows apart when the list changes */}
                {shown.map((row) => {
                  const isSelected = row.id === selectedId;
                  const decision = decisions[row.id];
                  const rejected = decision?.kind === "rejected";
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
                      className={`cursor-pointer border-t border-line-soft outline-none focus-visible:bg-subtle-strong ${
                        isSelected ? "bg-highlight-soft" : "hover:bg-subtle"
                      } ${rejected ? "opacity-50" : ""}`}
                    >
                      <td className="px-3 py-3">
                        {/* the decision sits right on the row, next to the status */}
                        <StatusBadge status={row.status} />
                        <DecisionMark decision={decision} />
                      </td>
                      <td className="px-3 py-3 text-ink">{row.material}</td>
                      <td className="px-3 py-3 text-muted">{row.property}</td>
                      <td className={`px-3 py-3 text-ink ${rejected ? "line-through" : ""}`}>
                        {decision?.kind === "edited" ? (
                          // edited: the researcher's number, with what Datum found struck through
                          <>
                            <span className="font-mono">{decision.value}</span>{" "}
                            <span className="font-mono text-xs text-faint line-through">{row.value}</span>
                          </>
                        ) : (
                          <span className="font-mono">{row.value}</span>
                        )}
                        {row.error !== "" && <span className="font-mono text-muted"> ± {row.error}</span>}
                        <span className="ml-1.5 text-xs text-soft">{row.unit}</span>
                      </td>
                      <td className="px-3 py-3 text-muted">p. {row.page}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
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

// A small mark after the status pill showing what the researcher decided.
// Nothing for untouched rows: verified ones are accepted automatically, and the pill already says so.
function DecisionMark({ decision }: { decision: Decision | undefined }) {
  if (decision === undefined) return null;
  const label = { accepted: "✓ accepted", edited: "✎ edited", rejected: "✕ rejected" }[decision.kind];
  return <span className="ml-2 text-xs text-muted">{label}</span>;
}
