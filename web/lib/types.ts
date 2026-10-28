// lib/types.ts
// The shape of Datum's data, written once and used everywhere in the frontend.
// It mirrors the columns in our Python schema.py, so frontend and backend agree.

// A "union type": status can ONLY be one of these three strings.
// Typing "verfied" anywhere in the app becomes a red error in VS Code.
export type Status = "verified" | "review" | "flagged";

// Where a value comes from: measured in this paper, or copied from one it cites.
export type Origin = "this paper" | "cited";

// One extracted value: one row of the results table.
// Field names stay snake_case to match the JSON our Python backend sends.
export type Row = {
  id: string; // unique id, so React can track each table row (needed for lists)
  status: Status;
  material: string; // exactly as the paper writes it, e.g. "PEDOT:PSS + EG"
  property: string; // as written, e.g. "[μC*]OECT"
  property_std: string; // which of the user's target properties it belongs to, e.g. "μC*"
  value: string; // copied exactly, e.g. "47" or "6.61 x 10-4" (string: never re-typed)
  error: string; // the ± part, or "" if none
  unit: string; // as written, e.g. "F cm−1 V−1 s−1"
  value_std: number | null; // converted to a standard unit; null if we don't know the unit
  error_std: number | null;
  unit_std: string;
  conditions: string; // how it was made/tested, or ""
  origin: Origin;
  reference: string; // citation number if origin is "cited", e.g. "19"
  paper: string; // file name of the paper
  page: number; // page the evidence is on
  evidence: string; // the exact quote or table row
  checks: string[]; // plain-English notes from verification
  provider: string; // which engine extracted it, e.g. "Cerebras"
};

// The five pipeline stages, in order. Drives the PipelineBar.
export type Stage = "ingest" | "filter" | "extract" | "verify" | "assemble";

// One extraction run: what the frontend polls while the pipeline works.
export type Run = {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  stage: Stage | null; // current stage while running; null before it starts
  detail: string; // e.g. "Extracting values · 2 of 3 parts"
  rows: Row[]; // filled in when status is "done"
};
