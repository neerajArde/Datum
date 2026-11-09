// lib/sample-run.ts
// PROTOTYPE: pretends to run the pipeline, so the UI can show live progress before the backend exists.
// It reports progress through onUpdate exactly the way the real backend will (a Run object),
// so when the backend arrives, only this file is replaced and the screens stay the same.

import type { Paper } from "./papers";
import type { Row, Run, Stage } from "./types";

type Step = { stage: Stage; detail: string; ms: number };

// Starts a fake run. Returns a function that cancels it (used if the researcher clicks Extract again,
// or leaves the page, so old timers never update a screen that's gone).
export function startSampleRun(papers: Paper[], rows: Row[], onUpdate: (run: Run) => void): () => void {
  const id = `sample-${Date.now()}`;
  const first = papers[0]?.file.name ?? "your paper";
  const more = papers.length > 1 ? ` and ${papers.length - 1} more` : "";

  // roughly the real pipeline's stages and messages, sped up
  const steps: Step[] = [
    { stage: "ingest", detail: `Reading ${first}${more}`, ms: 700 },
    { stage: "filter", detail: "Finding the pages that mention your properties", ms: 700 },
    { stage: "extract", detail: "Extracting values · 1 of 3 parts", ms: 500 },
    { stage: "extract", detail: "Extracting values · 2 of 3 parts", ms: 500 },
    { stage: "extract", detail: "Extracting values · 3 of 3 parts", ms: 500 },
    { stage: "verify", detail: `Checking ${rows.length} values against the PDFs`, ms: 700 },
    { stage: "assemble", detail: "Building the table", ms: 500 },
  ];

  const timers: ReturnType<typeof setTimeout>[] = [];
  onUpdate({ id, status: "queued", stage: null, detail: "Starting", rows: [] });

  let at = 0;
  for (const step of steps) {
    timers.push(setTimeout(() => onUpdate({ id, status: "running", stage: step.stage, detail: step.detail, rows: [] }), at));
    at += step.ms;
  }
  const paperWord = papers.length === 1 ? "paper" : "papers";
  timers.push(
    setTimeout(
      () => onUpdate({ id, status: "done", stage: "assemble", detail: `${rows.length} values from ${papers.length} ${paperWord}`, rows }),
      at,
    ),
  );

  return () => timers.forEach(clearTimeout);
}
