// components/FilterButtons.tsx
// The All / Verified / Review / Flagged buttons above the table.
// It does NOT remember which one is selected - its parent (ResultsTable) does.
// This component only draws the buttons and reports clicks back up.

import type { Status } from "@/lib/types";

// A filter is either "all" or one of the three statuses.
export type Filter = "all" | Status;

const OPTIONS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "verified", label: "Verified" },
  { value: "review", label: "Review" },
  { value: "flagged", label: "Flagged" },
];

type Props = {
  selected: Filter; //                      which button is on (a prop: the parent owns it)
  counts: Record<Filter, number>; //        how many rows each button would show
  onPick: (filter: Filter) => void; //      the parent's function to call when a button is clicked
};

export default function FilterButtons({ selected, counts, onPick }: Props) {
  return (
    <div className="inline-flex gap-1 rounded-lg border border-zinc-200 bg-white p-1">
      {OPTIONS.map((option) => {
        const isOn = option.value === selected;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onPick(option.value)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              isOn ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
            }`}
          >
            {option.label}
            <span className={`ml-1.5 ${isOn ? "text-zinc-300" : "text-zinc-400"}`}>
              {counts[option.value]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
