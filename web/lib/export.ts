// lib/export.ts
// Turns the reviewed rows into a CSV file. Pure logic, no UI, so it's easy to test.

import type { Row } from "./types";
import type { Decisions } from "./review";

// Which rows go into the file:
//   - rejected by the researcher        -> never
//   - accepted or edited by them        -> always (they vouched for it, even if it was flagged)
//   - no decision yet: verified         -> yes (accepted automatically)
//                      review          -> only if includeReview is on
//                      flagged         -> no (likely wrong)
export function isExported(row: Row, decisions: Decisions, includeReview: boolean): boolean {
  const decision = decisions[row.id];
  if (decision?.kind === "rejected") return false;
  if (decision !== undefined) return true;
  if (row.status === "verified") return true;
  if (row.status === "review") return includeReview;
  return false;
}

// The counts shown next to the Download button.
export function exportSummary(rows: Row[], decisions: Decisions, includeReview: boolean) {
  const undecided = (status: Row["status"]) =>
    rows.filter((row) => row.status === status && decisions[row.id] === undefined).length;
  return {
    included: rows.filter((row) => isExported(row, decisions, includeReview)).length,
    reviewLeftOut: includeReview ? 0 : undecided("review"),
    reviewIncluded: includeReview ? undecided("review") : 0,
    flaggedLeftOut: undecided("flagged"),
  };
}

// Column order in the file. Every row keeps its receipt: paper, page, quote, checks.
const COLUMNS = [
  "status", "decision", "material", "property", "property_std",
  "value", "original_value", "error", "unit", "value_std", "unit_std",
  "conditions", "origin", "reference", "paper", "page", "evidence", "checks",
] as const;

// One CSV cell. Quotes every cell and doubles any quotes inside it, so commas and
// line breaks in a quote can't break the columns.
function cell(raw: string | number | null): string {
  let text = raw === null ? "" : String(raw);
  // Spreadsheet safety: Excel runs a cell starting with = + @ as a FORMULA ("CSV injection").
  // A quote from a paper should never execute, so we put an apostrophe in front.
  // (A leading "-" is fine for real numbers like -0.5, so we only guard "-" when it's text.)
  if (/^[=+@\t\r]/.test(text) || (/^-/.test(text) && Number.isNaN(Number(text)))) text = "'" + text;
  return `"${text.replace(/"/g, '""')}"`;
}

export function toCsv(rows: Row[], decisions: Decisions, includeReview: boolean): string {
  const lines: string[] = [COLUMNS.join(",")];
  for (const row of rows) {
    if (!isExported(row, decisions, includeReview)) continue;
    const decision = decisions[row.id];
    const edited = decision?.kind === "edited";
    const values: Record<(typeof COLUMNS)[number], string | number | null> = {
      status: row.status,
      decision: decision?.kind ?? (row.status === "verified" ? "auto-accepted" : "undecided"),
      material: row.material,
      property: row.property,
      property_std: row.property_std,
      value: edited ? decision.value : row.value, // the corrected number, if there is one
      original_value: edited ? row.value : "", //  what Datum found, kept so the change is traceable
      error: row.error,
      unit: row.unit,
      value_std: edited ? null : row.value_std, // a corrected value hasn't been re-converted yet
      unit_std: row.unit_std,
      conditions: row.conditions,
      origin: row.origin,
      reference: row.reference,
      paper: row.paper,
      page: row.page,
      evidence: row.evidence,
      checks: row.checks.join("; "),
    };
    lines.push(COLUMNS.map((column) => cell(values[column])).join(","));
  }
  // "﻿" (a byte-order mark) tells Excel the file is UTF-8, so μ, ±, ⁻¹ show up correctly
  return "﻿" + lines.join("\r\n") + "\r\n";
}

// Hands the text to the browser as a file download.
export function downloadCsv(csv: string, fileName: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob); // a temporary link to the file in memory
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url); // free the memory
}
