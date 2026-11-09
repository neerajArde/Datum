// components/TriageBar.tsx
// The overview after a run: how many values are verified / to review / flagged.
// Verified values are accepted automatically; only review + flagged values need the researcher.

import type { Row, Status } from "@/lib/types";
import { needsDecision, type Decisions } from "@/lib/review";
import Button from "./ui/Button";
import Card from "./ui/Card";

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
    <Card as="section" className="space-y-4 p-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Group
          dot="bg-verified"
          label="verified"
          count={total("verified")}
          note="accepted automatically"
          actions={
            <Button variant="secondary" onClick={onSpotCheck} disabled={total("verified") === 0}>
              Spot-check 5
            </Button>
          }
        />
        <Group
          dot="bg-review"
          label="to review"
          count={total("review")}
          note={`${open("review")} left`}
          actions={
            <Button onClick={() => onReview(["review"])} disabled={open("review") === 0}>
              Start reviewing →
            </Button>
          }
        />
        <Group
          dot="bg-flagged"
          label="flagged"
          count={total("flagged")}
          note={`${open("flagged")} left`}
          actions={
            <Button onClick={() => onReview(["flagged"])} disabled={open("flagged") === 0}>
              Start reviewing →
            </Button>
          }
        />
      </div>

      <div>
        <div className="mb-1 flex justify-between text-xs text-soft">
          <span>Your decisions</span>
          <span>
            {needing.length === 0 ? "nothing needs you" : `${decided} of ${needing.length} done`}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-subtle-strong">
          <div className="h-full rounded-full bg-ink transition-all" style={{ width: `${percent}%` }} />
        </div>
      </div>
    </Card>
  );
}


// one column of the bar: a colored dot, the count, a small note, and the buttons
function Group(props: { dot: string; label: string; count: number; note: string; actions: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg bg-subtle p-4">
      <p className="flex items-center gap-2 text-sm text-muted">
        <span className={`h-2 w-2 rounded-full ${props.dot}`} />
        <span className="text-xl font-semibold text-ink">{props.count}</span> {props.label}
        <span className="ml-auto text-xs text-faint">{props.note}</span>
      </p>
      <div className="flex flex-wrap gap-2">{props.actions}</div>
    </div>
  );
}
