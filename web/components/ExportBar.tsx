// components/ExportBar.tsx
// The fast path: download the table straight away, no review needed.
// Default = verified values only; review values can be added with one click; flagged are left out
// unless the researcher accepts them in review.

import type { Row } from "@/lib/types";
import type { Decisions } from "@/lib/review";
import { downloadCsv, exportSummary, toCsv } from "@/lib/export";

type Props = {
  rows: Row[];
  decisions: Decisions;
  includeReview: boolean; //                          the switch lives in the parent (Workspace)
  onIncludeReviewChange: (include: boolean) => void;
};

export default function ExportBar({ rows, decisions, includeReview, onIncludeReviewChange }: Props) {
  const summary = exportSummary(rows, decisions, includeReview);

  function download() {
    // the researcher's own date (toISOString would give UTC, which is "tomorrow" in the evening in the US)
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`; // e.g. 2026-11-08
    downloadCsv(toCsv(rows, decisions, includeReview), `datum-export-${today}.csv`);
  }

  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-zinc-200 bg-white px-5 py-4">
      <div className="space-y-1 text-sm">
        <p className="text-zinc-900">
          <span className="font-semibold">{summary.included} values</span> in your download
          {summary.reviewLeftOut > 0 && (
            <>
              {" · "}
              <span className="text-amber-800">{summary.reviewLeftOut} left out for review</span>{" "}
              <button type="button" onClick={() => onIncludeReviewChange(true)} className="font-medium underline underline-offset-2">
                Include them
              </button>
            </>
          )}
          {summary.reviewIncluded > 0 && (
            <>
              {" · "}
              <span className="text-amber-800">including {summary.reviewIncluded} still to review</span> (marked in the status column){" "}
              <button type="button" onClick={() => onIncludeReviewChange(false)} className="font-medium underline underline-offset-2">
                Leave them out
              </button>
            </>
          )}
        </p>
        {summary.flaggedLeftOut > 0 && (
          <p className="text-zinc-500">
            {summary.flaggedLeftOut} flagged {summary.flaggedLeftOut === 1 ? "value" : "values"} left out (likely wrong)
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={download}
        disabled={summary.included === 0}
        className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
      >
        Download CSV
      </button>
    </section>
  );
}
