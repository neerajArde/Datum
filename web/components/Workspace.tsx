// components/Workspace.tsx
// Holds the review session: every decision made, and which values are being reviewed.
// Shows the triage bar on top, then either review mode (the evidence panel in focus size,
// one value at a time) or the full results table (the same panel in compact size).
// PROTOTYPE: decisions live in memory only, so a refresh clears them. Saving comes with the backend.

"use client";

import { useState } from "react";
import type { Row, Status } from "@/lib/types";
import type { Decision, Decisions } from "@/lib/review";
import TriageBar from "./TriageBar";
import EvidencePanel from "./EvidencePanel";
import ResultsTable from "./ResultsTable";

export default function Workspace({ rows }: { rows: Row[] }) {
  // STATE: every decision so far (row id -> decision)
  const [decisions, setDecisions] = useState<Decisions>({});
  // STATE: the review queue (row ids to go through) and where we are in it. null = no review running.
  const [queue, setQueue] = useState<string[] | null>(null);
  const [position, setPosition] = useState(0);

  // record a decision. A NEW object, so React notices the change.
  function record(id: string, decision: Decision) {
    setDecisions({ ...decisions, [id]: decision });
  }

  // in review mode, deciding also moves on to the next value
  function decideAndAdvance(id: string, decision: Decision) {
    record(id, decision);
    setPosition(position + 1);
  }

  function acceptAllVerified() {
    const next = { ...decisions };
    for (const row of rows) {
      if (row.status === "verified" && !next[row.id]) next[row.id] = { kind: "accepted" };
    }
    setDecisions(next);
  }

  function startReview(statuses: Status[]) {
    setQueue(rows.filter((row) => statuses.includes(row.status) && !decisions[row.id]).map((row) => row.id));
    setPosition(0);
  }

  function startSpotCheck() {
    // 5 random verified values nobody has decided on yet
    const open = rows.filter((row) => row.status === "verified" && !decisions[row.id]);
    const shuffled = [...open].sort(() => Math.random() - 0.5);
    setQueue(shuffled.slice(0, 5).map((row) => row.id));
    setPosition(0);
  }

  const current = queue !== null ? rows.find((row) => row.id === queue[position]) : undefined;

  return (
    <div className="space-y-6">
      <TriageBar
        rows={rows}
        decisions={decisions}
        onAcceptAllVerified={acceptAllVerified}
        onSpotCheck={startSpotCheck}
        onReview={startReview}
      />

      {queue === null ? (
        <ResultsTable rows={rows} decisions={decisions} onDecide={record} />
      ) : current !== undefined ? (
        <EvidencePanel
          // key: a new row = a fresh panel, so its edit box and "more notes" start closed
          key={current.id}
          row={current}
          decision={decisions[current.id]}
          onDecide={(decision) => decideAndAdvance(current.id, decision)}
          review={{
            position: position + 1,
            total: queue.length,
            onPrevious: () => setPosition(Math.max(0, position - 1)),
            onNext: () => setPosition(Math.min(queue.length, position + 1)),
            onExit: () => setQueue(null),
          }}
        />
      ) : (
        <DoneCard queue={queue} decisions={decisions} onBack={() => setQueue(null)} />
      )}
    </div>
  );
}

// shown when the queue is finished
function DoneCard(props: { queue: string[]; decisions: Decisions; onBack: () => void }) {
  const kinds = props.queue.map((id) => props.decisions[id]?.kind);
  const count = (kind: Decision["kind"]) => kinds.filter((k) => k === kind).length;
  const skipped = kinds.filter((k) => k === undefined).length;
  return (
    <section className="space-y-4 rounded-xl border border-zinc-200 bg-white p-8 text-center">
      <p className="text-2xl font-semibold text-zinc-900">Review done</p>
      <p className="text-sm text-zinc-600">
        {count("accepted")} accepted · {count("edited")} edited · {count("rejected")} rejected
        {skipped > 0 && <> · {skipped} skipped</>}
      </p>
      <button type="button" onClick={props.onBack} className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white">
        Back to table
      </button>
    </section>
  );
}
