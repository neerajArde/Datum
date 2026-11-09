// components/Workspace.tsx
// The whole thread: the composer on top; on Extract, the pipeline bar shows progress;
// when the run is done, the results appear below (download bar, triage, then the table or review mode).
// Holds the review session: every decision made, and which values are being reviewed.
// Shows the triage bar on top, then either review mode (the evidence panel in focus size,
// one value at a time) or the full results table (the same panel in compact size).
// PROTOTYPE: decisions live in memory only, so a refresh clears them. Saving comes with the backend.

"use client";

import { useEffect, useRef, useState } from "react";
import type { Row, Run, Status } from "@/lib/types";
import type { Paper } from "@/lib/papers";
import { startSampleRun } from "@/lib/sample-run";
import type { Decision, Decisions } from "@/lib/review";
import TriageBar from "./TriageBar";
import ExportBar from "./ExportBar";
import Composer from "./Composer";
import PipelineBar from "./PipelineBar";
import EvidencePanel from "./EvidencePanel";
import ResultsTable from "./ResultsTable";
import Button from "./ui/Button";
import Card from "./ui/Card";

// sampleRows: what the PROTOTYPE run returns. The real backend will return the real rows instead.
export default function Workspace({ sampleRows }: { sampleRows: Row[] }) {
  // STATE: every decision so far (row id -> decision)
  const [decisions, setDecisions] = useState<Decisions>({});
  // STATE: the review queue (row ids to go through) and where we are in it. null = no review running.
  const [queue, setQueue] = useState<string[] | null>(null);
  const [position, setPosition] = useState(0);
  // STATE: should the download include values still waiting for review? Default: no (verified only).
  const [includeReview, setIncludeReview] = useState(false);
  // STATE: the current run (null = Extract not clicked yet). It moves queued -> running -> done.
  const [run, setRun] = useState<Run | null>(null);

  // A REF holding the "cancel" function of the run in progress. A ref (not state) because changing it
  // shouldn't redraw anything; we only need to remember it.
  const cancelRun = useRef<(() => void) | null>(null);

  // when the page goes away, stop any run so its timers don't update a screen that no longer exists
  useEffect(() => () => cancelRun.current?.(), []);

  function extract(input: { properties: string; papers: Paper[] }) {
    cancelRun.current?.(); // a new Extract replaces any run still going
    // new results = a fresh review session
    setDecisions({});
    setQueue(null);
    setPosition(0);
    // PROTOTYPE: fake progress, then the sample rows. Later: send papers + properties to the backend.
    cancelRun.current = startSampleRun(input.papers, sampleRows, setRun);
  }

  const running = run !== null && (run.status === "queued" || run.status === "running");
  // the rows on screen are whatever the finished run returned
  const rows = run?.status === "done" ? run.rows : [];

  // record a decision. A NEW object, so React notices the change.
  function record(id: string, decision: Decision) {
    setDecisions({ ...decisions, [id]: decision });
  }

  // in review mode, deciding also moves on to the next value
  function decideAndAdvance(id: string, decision: Decision) {
    record(id, decision);
    setPosition(position + 1);
  }

  function startReview(statuses: Status[]) {
    setQueue(rows.filter((row) => statuses.includes(row.status) && !decisions[row.id]).map((row) => row.id));
    setPosition(0);
  }

  function startSpotCheck() {
    // 5 random verified values the researcher hasn't touched yet, to confirm "verified" can be trusted
    const open = rows.filter((row) => row.status === "verified" && !decisions[row.id]);
    const shuffled = [...open].sort(() => Math.random() - 0.5);
    setQueue(shuffled.slice(0, 5).map((row) => row.id));
    setPosition(0);
  }

  const current = queue !== null ? rows.find((row) => row.id === queue[position]) : undefined;

  return (
    <div className="space-y-6">
      {/* ONE composer, always in the same spot. (Rendering it in two different places would make React
          treat them as two different composers, and the added papers would vanish on Extract.) */}
      <Composer onExtract={extract} busy={running} />

      {/* progress, from the moment Extract is clicked */}
      {run !== null && <PipelineBar run={run} />}

      {/* everything below appears once the run is done */}
      {run?.status === "done" && (
        <>
          <p className="text-sm text-soft">Showing sample results. The real extraction arrives with the backend.</p>

          {/* the fast path first: most researchers just want the table */}
          <ExportBar rows={rows} decisions={decisions} includeReview={includeReview} onIncludeReviewChange={setIncludeReview} />

          <TriageBar rows={rows} decisions={decisions} onSpotCheck={startSpotCheck} onReview={startReview} />

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
        </>
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
    <Card as="section" className="space-y-4 p-8 text-center">
      <p className="text-2xl font-semibold text-ink">Review done</p>
      <p className="text-sm text-muted">
        {count("accepted")} accepted · {count("edited")} edited · {count("rejected")} rejected
        {skipped > 0 && <> · {skipped} skipped</>}
      </p>
      <Button onClick={props.onBack} size="lg">
        Back to table
      </Button>
    </Card>
  );
}
