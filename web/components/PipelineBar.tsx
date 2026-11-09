// components/PipelineBar.tsx
// Live progress of a run through Datum's five stages. A capsule slides to the current stage,
// finished stages get a ✓, and the line underneath says what's happening right now.
// It only DISPLAYS a Run; it doesn't know whether the run is fake (today) or real (backend).

import type { Run, Stage } from "@/lib/types";
import Card from "./ui/Card";

const STAGES: { key: Stage; label: string }[] = [
  { key: "ingest", label: "Ingest" },
  { key: "filter", label: "Filter" },
  { key: "extract", label: "Extract" },
  { key: "verify", label: "Verify" },
  { key: "assemble", label: "Assemble" },
];

export default function PipelineBar({ run }: { run: Run }) {
  const done = run.status === "done";
  const failed = run.status === "failed";
  const current = run.stage === null ? -1 : STAGES.findIndex((stage) => stage.key === run.stage);

  return (
    <Card as="section" className="p-3">
      <ol className="relative grid grid-cols-5">
        {/* the capsule: one-fifth wide, slid along by `current` fifths. motion-reduce = respect
            people who turned off animations in their system settings */}
        {!done && current >= 0 && (
          <div
            aria-hidden
            className={`absolute inset-y-0 left-0 w-1/5 rounded-lg transition-transform duration-500 ease-out motion-reduce:transition-none ${
              failed ? "bg-flagged-bg" : "bg-subtle-strong"
            }`}
            style={{ transform: `translateX(${current * 100}%)` }}
          />
        )}
        {STAGES.map((stage, index) => {
          const state = done || index < current ? "done" : index === current ? "active" : "todo";
          return (
            <li
              key={stage.key}
              aria-current={state === "active" ? "step" : undefined}
              className={`relative flex items-center justify-center gap-1.5 py-2 text-sm ${
                state === "todo" ? "text-faint" : state === "active" ? "font-medium text-ink" : "text-muted"
              }`}
            >
              {state === "done" && <span className="text-verified">✓</span>}
              {state === "active" && !failed && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink motion-reduce:animate-none" />
              )}
              {stage.label}
            </li>
          );
        })}
      </ol>
      {/* role="status": screen readers read out each new message as the run moves on */}
      <p role="status" aria-live="polite" className={`mt-1 text-center text-sm ${failed ? "text-flagged-ink" : "text-soft"}`}>
        {done ? `Done · ${run.detail}` : run.detail}
      </p>
    </Card>
  );
}
