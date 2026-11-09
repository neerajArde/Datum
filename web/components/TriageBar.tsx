// components/TriageBar.tsx
// The overview after a run: how many values are verified / to review / flagged,
// with one-click actions for each group and a progress bar of decisions made.

import type { Row, Status } from "@/lib/types";
import type { Decisions } from "@/lib/review";

type Props = {
  rows: Row[];
  decisions: Decisions;
  onAcceptAllVerified: () => void;
  onSpotCheck: () => void;
  onReview: (statuses: Status[]) => void;
};

export default function TriageBar({ rows, decisions, onAcceptAllVerified, onSpotCheck, onReview }: Props) {
  // how many rows of a status are still waiting for a decision
  const open = (status: Status) => rows.filter((row) => row.status === status && !decisions[row.id]).length;
  const total = (status: Status) => rows.filter((row) => row.status === status).length;
  const decided = Object.keys(decisions).length;
  const percent = rows.length === 0 ? 0 : Math.round((decided / rows.length) * 100);

  return (
    <section className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Group
          dot="bg-emerald-500"
          label="verified"
          count={total("verified")}
          left={open("verified")}
          actions={
            <>
              <button type="button" onClick={onSpotCheck} disabled={open("verified") === 0} className={secondary}>
                Spot-check 5
              </button>
              <button type="button" onClick={onAcceptAllVerified} disabled={open("verified") === 0} className={primary}>
                Accept all {open("verified")}
              </button>
            </>
          }
        />
        <Group
          dot="bg-amber-500"
          label="to review"
          count={total("review")}
          left={open("review")}
          actions={
            <button type="button" onClick={() => onReview(["review"])} disabled={open("review") === 0} className={primary}>
              Start reviewing →
            </button>
          }
        />
        <Group
          dot="bg-red-500"
          label="flagged"
          count={total("flagged")}
          left={open("flagged")}
          actions={
            <button type="button" onClick={() => onReview(["flagged"])} disabled={open("flagged") === 0} className={primary}>
              Start reviewing →
            </button>
          }
        />
      </div>

      <div>
        <div className="mb-1 flex justify-between text-xs text-zinc-500">
          <span>Review progress</span>
          <span>
            {decided} / {rows.length} decided
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-zinc-100">
          <div className="h-full rounded-full bg-zinc-900 transition-all" style={{ width: `${percent}%` }} />
        </div>
      </div>
    </section>
  );
}

const primary =
  "rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-30";
const secondary =
  "rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-30";

// one column of the bar: a colored dot, the count, how many are left, and the buttons
function Group(props: { dot: string; label: string; count: number; left: number; actions: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg bg-zinc-50 p-4">
      <p className="flex items-center gap-2 text-sm text-zinc-600">
        <span className={`h-2 w-2 rounded-full ${props.dot}`} />
        <span className="text-xl font-semibold text-zinc-900">{props.count}</span> {props.label}
        <span className="ml-auto text-xs text-zinc-400">{props.left} left</span>
      </p>
      <div className="flex flex-wrap gap-2">{props.actions}</div>
    </div>
  );
}
