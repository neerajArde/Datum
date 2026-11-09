// components/TriageBar.tsx
// The overview after a run: how many values are verified / to review / flagged.
// Verified values are accepted automatically; only review + flagged values need the researcher.

import type { Row, Status } from "@/lib/types";
import { needsDecision, type Decisions } from "@/lib/review";

type Props = {
  rows: Row[];
  decisions: Decisions;
  onSpotCheck: () => void;
  onReview: (statuses: Status[]) => void;
};

export default function TriageBar({ rows, decisions, onSpotCheck, onReview }: Props) {
  // how many rows of a status are still waiting for a decision
  const open = (status: Status) => rows.filter((row) => row.status === status && !decisions[row.id]).length;
  const total = (status: Status) => rows.filter((row) => row.status === status).length;
  // progress counts ONLY the values that need a human
  const needing = rows.filter(needsDecision);
  const decided = needing.filter((row) => decisions[row.id] !== undefined).length;
  const percent = needing.length === 0 ? 100 : Math.round((decided / needing.length) * 100);

  return (
    <section className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Group
          dot="bg-emerald-500"
          label="verified"
          count={total("verified")}
          note="accepted automatically"
          actions={
            <button type="button" onClick={onSpotCheck} disabled={total("verified") === 0} className={secondary}>
              Spot-check 5
            </button>
          }
        />
        <Group
          dot="bg-amber-500"
          label="to review"
          count={total("review")}
          note={`${open("review")} left`}
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
          note={`${open("flagged")} left`}
          actions={
            <button type="button" onClick={() => onReview(["flagged"])} disabled={open("flagged") === 0} className={primary}>
              Start reviewing →
            </button>
          }
        />
      </div>

      <div>
        <div className="mb-1 flex justify-between text-xs text-zinc-500">
          <span>Your decisions</span>
          <span>
            {needing.length === 0 ? "nothing needs you" : `${decided} of ${needing.length} done`}
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

// one column of the bar: a colored dot, the count, a small note, and the buttons
function Group(props: { dot: string; label: string; count: number; note: string; actions: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg bg-zinc-50 p-4">
      <p className="flex items-center gap-2 text-sm text-zinc-600">
        <span className={`h-2 w-2 rounded-full ${props.dot}`} />
        <span className="text-xl font-semibold text-zinc-900">{props.count}</span> {props.label}
        <span className="ml-auto text-xs text-zinc-400">{props.note}</span>
      </p>
      <div className="flex flex-wrap gap-2">{props.actions}</div>
    </div>
  );
}
