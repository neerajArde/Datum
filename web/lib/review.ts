// lib/review.ts
// "Smart notes" for reviewing a value, written as plain code - no AI.
// 1. Rewrites the verifier's raw checks into plain English, sorted by how much they matter.
// 2. Reads the WORDING around the value for traps: "respectively", "up to", ranges, "~".
// 3. Sums it all up in one verdict line: can I use this number?

import type { Row } from "./types";
import { splitAtValue } from "./highlight";

// How much a note matters. Blockers first, then cautions, then info.
export type Level = "blocker" | "caution" | "info";
export type Note = { level: Level; text: string };

// What the reviewer decided. An edit keeps the original value in the row and stores the fix here,
// so we always know what Datum found AND what the human changed it to.
export type Decision = { kind: "accepted" } | { kind: "rejected" } | { kind: "edited"; value: string };
export type Decisions = Record<string, Decision>; // row id -> decision

// ---------- 1. raw checks -> plain-English notes ----------
// Each rule: if the check contains this text, it becomes this note.
const CHECK_RULES: { contains: string; level: Level; text: string }[] = [
  { contains: "evidence not found", level: "blocker", text: "The quote wasn't found in the paper, so this value may be invented." },
  { contains: "value not in evidence", level: "blocker", text: "The number isn't in the quoted text. It may be misread or invented." },
  { contains: "doesn't fit this property", level: "blocker", text: "The unit doesn't fit this property, so it may be a different measurement." },
  { contains: "no value", level: "blocker", text: "No value was extracted." },
  { contains: "value is not a single number", level: "caution", text: "This isn't a single number. Decide what to record." },
  { contains: "error value not in evidence", level: "caution", text: "The ± error isn't in the quote." },
  { contains: "only approximately matches", level: "caution", text: "The quote only roughly matches the paper's text. Compare it with the page." },
  { contains: "not one of your target properties", level: "caution", text: "This isn't one of the properties you asked for." },
  { contains: "no material name", level: "caution", text: "No material name. Check which material this belongs to." },
  { contains: "no unit", level: "caution", text: "No unit was given." },
  { contains: "evidence too short", level: "caution", text: "The quote is too short to check reliably." },
  { contains: "material named outside", level: "info", text: "The material is named outside this sentence (usually fine)." },
  { contains: "no conditions stated", level: "info", text: "No measurement conditions were found." },
  { contains: "kept as written", level: "info", text: "The unit isn't in Datum's standard list, so it's kept as written." },
  { contains: "matched as a table row", level: "info", text: "Found as a table row: material and value appear together." },
  { contains: "page corrected", level: "info", text: "The page number was corrected." },
];

function noteForCheck(check: string): Note | null {
  const lower = check.toLowerCase();
  // the "cited" checks are handled separately, as a stronger, actionable note
  if (lower.includes("originally reported")) return null;
  for (const rule of CHECK_RULES) {
    if (lower.includes(rule.contains)) return { level: rule.level, text: rule.text };
  }
  return { level: "caution", text: check }; // unknown check: show it as written
}

// ---------- 2. traps in the wording around the value ----------
function wordingNotes(row: Row): Note[] {
  const notes: Note[] = [];
  const parts = splitAtValue(row.evidence, row.value);
  const before = parts ? parts[0].slice(-40) : "";
  const after = parts ? parts[2].slice(0, 25) : "";

  if (/respectively/i.test(row.evidence)) {
    notes.push({
      level: "caution",
      text: `This sentence pairs several values with "respectively". Check that ${row.value} is matched to the right property and material.`,
    });
  }
  if (/(up to|as high as|maximum of|max\.?|reaching|exceeding|over|above|>|≥)\s*$/i.test(before)) {
    notes.push({ level: "caution", text: `The paper says "up to ${row.value}": that's a maximum, not a typical value.` });
  }
  if (/\d\s*(to|–|—)\s*$/i.test(before) || /^\s*(to|–|—)\s*\d/i.test(after)) {
    notes.push({ level: "caution", text: `${row.value} is one end of a range in the paper, not a single measurement.` });
  }
  if (/^[~≈]/.test(row.value) || /(~|≈|about|approximately|around|roughly|nearly)\s*$/i.test(before)) {
    notes.push({ level: "caution", text: "The paper gives this as an approximate value." });
  }
  return notes;
}

// ---------- put it together ----------
const ORDER: Record<Level, number> = { blocker: 0, caution: 1, info: 2 };

export function notesFor(row: Row): Note[] {
  const notes: Note[] = [...wordingNotes(row)];
  if (row.origin === "cited") {
    const ref = row.reference !== "" ? ` (reference [${row.reference}])` : "";
    notes.push({ level: "caution", text: `Quoted from another paper${ref}. The original source is the better citation.` });
  }
  for (const check of row.checks) {
    const note = noteForCheck(check);
    if (note !== null && !notes.some((n) => n.text === note.text)) notes.push(note);
  }
  // stable sort: blockers first, then cautions, then info
  return notes.sort((a, b) => ORDER[a.level] - ORDER[b.level]);
}

// One sentence that answers "can I use this number?"
export type Verdict = { tone: "good" | "careful" | "stop"; text: string };

export function verdictFor(row: Row, notes: Note[]): Verdict {
  const first = notes[0];
  if (first !== undefined && first.level === "blocker") {
    return { tone: "stop", text: `Don't use this yet. ${first.text}` };
  }
  if (first !== undefined && first.level === "caution") {
    return { tone: "careful", text: `Check before using. ${first.text}` };
  }
  return { tone: "good", text: "Matches the paper exactly. Safe to accept." };
}
