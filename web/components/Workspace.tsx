// components/Workspace.tsx
// One thread's screen: the composer on top; on Extract, the pipeline bar shows progress;
// when the run is done, the results appear below (download bar, triage, then the table or review mode).
// Holds the review session: every decision made, and which values are being reviewed.
// Shows the triage bar on top, then either review mode (the evidence panel in focus size,
// one value at a time) or the full results table (the same panel in compact size).
// The thread's data lives in ThreadsShell; this component only draws it and reports changes.

"use client";

import { useState } from "react";
import type { Status } from "@/lib/types";
import type { Paper } from "@/lib/papers";
import { isRunning, isStale, type Thread, type ThreadPatch } from "@/lib/threads";
import type { Decision, Decisions } from "@/lib/review";
import TriageBar from "./TriageBar";
import ExportBar from "./ExportBar";
import Composer from "./Composer";
import PipelineBar from "./PipelineBar";
import EvidencePanel from "./EvidencePanel";
import ResultsTable from "./ResultsTable";
import Button from "./ui/Button";
import Card from "./ui/Card";

type Props = {
  thread: Thread; //                               this thread's data, owned by ThreadsShell
  onChange: (patch: ThreadPatch) => void; //        change this thread (decisions, properties)
  onPapersChange: (papers: Paper[]) => void; //    papers also update the automatic title, so they get their own callback
  onExtract: () => void; //                        start a run for this thread
};

export default function Workspace({ thread, onChange, onPapersChange, onExtract }: Props) {
  // The thread's DATA (papers, run, decisions) comes in as props from ThreadsShell.
  // Only screen state that doesn't need saving lives here:
  // STATE: the review queue (row ids to go through) and where we are in it. null = no review running.
  const [queue, setQueue] = useState<string[] | null>(null);
  const [position, setPosition] = useState(0);
  // STATE: should the download include values still waiting for review? Default: no (verified only).
  const [includeReview, setIncludeReview] = useState(false);

  const decisions = thread.decisions;
  const run = thread.run;
  const running = isRunning(thread);
  // the rows on screen are whatever the finished run returned
  const rows = run?.status === "done" ? run.rows : [];

  function extract() {
    // a new run means new results, so close any review in progress
    setQueue(null);
    setPosition(0);
    onExtract();
  }

  // record a decision. The function form uses the thread's LATEST decisions, so two quick
  // key presses in review mode can't overwrite each other. A NEW object, so React notices the change.
  function record(id: string, decision: Decision) {
    onChange((current) => ({ decisions: { ...current.decisions, [id]: decision } }));
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
      <Composer
        properties={thread.properties}
        papers={thread.papers}
        onPropertiesChange={(properties) => onChange({ properties })}
        onPapersChange={onPapersChange}
        onExtract={extract}
        busy={running}
        stale={isStale(thread)}
      />

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
