// components/StatusBadge.tsx
// The small colored pill that shows a row's verdict: verified / review / flagged.
// Reused in the results table now, and in the evidence card later.

import type { Status } from "@/lib/types";

// Record<Status, string> means: "one entry for EVERY status, no more, no less".
// If we ever add a fourth status to types.ts, TypeScript makes us add its color here.
const STYLES: Record<Status, string> = {
  verified: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  review: "bg-amber-50 text-amber-800 ring-amber-600/20",
  flagged: "bg-red-50 text-red-700 ring-red-600/20",
};

export default function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[status]}`}
    >
      {status}
    </span>
  );
}
