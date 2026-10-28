// components/EvidenceCard.tsx
// The "receipt" for one value: where it came from, the exact quote with the value
// highlighted, and what verification noticed. It only displays - it remembers nothing.

import type { Row } from "@/lib/types";
import StatusBadge from "./StatusBadge";

// Splits the quote around the value so we can highlight it, e.g.
// "exhibits a µC* of 47 ± 6"  ->  ["exhibits a µC* of ", "47", " ± 6"].
// Returns null if the value isn't in the quote (then we show the quote without a highlight).
function splitAtValue(quote: string, value: string): [string, string, string] | null {
  if (value === "") return null;
  // escape characters like "." and "*" so they're matched literally
  const escaped = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // match the value as a whole number: "47" must not match inside "147" or "4.7"
  const match = new RegExp(`(?<![\\d.])${escaped}(?!\\d)`).exec(quote);
  if (match === null) return null;
  const start = match.index;
  const end = start + value.length;
  return [quote.slice(0, start), quote.slice(start, end), quote.slice(end)];
}

export default function EvidenceCard({ row }: { row: Row | null }) {
  // nothing selected yet: a gentle hint instead of an empty box
  if (row === null) {
    return (
      <aside className="rounded-xl border border-dashed border-zinc-300 p-6 text-sm text-zinc-500">
        Select a row to see where its value came from.
      </aside>
    );
  }

  const parts = splitAtValue(row.evidence, row.value);

  return (
    <aside className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-zinc-500">
          {row.material} · {row.property_std || row.property}
        </p>
        <StatusBadge status={row.status} />
      </div>

      <p className="text-3xl font-semibold tracking-tight text-zinc-900">
        {row.value}
        {row.error !== "" && <span className="text-zinc-500"> ± {row.error}</span>}
        <span className="ml-2 text-base font-normal text-zinc-500">{row.unit}</span>
      </p>

      {/* the quote, with the value marked in yellow */}
      <blockquote className="border-l-2 border-yellow-300 pl-4 font-serif text-base leading-relaxed text-zinc-800">
        {parts === null ? (
          row.evidence
        ) : (
          <>
            {parts[0]}
            <mark className="rounded bg-yellow-200 px-0.5 text-zinc-900">{parts[1]}</mark>
            {parts[2]}
          </>
        )}
      </blockquote>

      <p className="text-sm text-zinc-600">
        Page {row.page} of {row.paper}
        {row.origin === "cited" && row.reference !== "" && (
          <span> · originally from reference [{row.reference}]</span>
        )}
      </p>

      {row.checks.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-600">
          {row.checks.map((check) => (
            <li key={check}>{check}</li>
          ))}
        </ul>
      )}

      <p className="text-xs text-zinc-400">Extracted by {row.provider}</p>
    </aside>
  );
}
