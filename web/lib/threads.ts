// lib/threads.ts
// A thread = one piece of work: its properties, its papers, its run and the decisions made on it.
// PROTOTYPE: threads live in the browser's memory, so a refresh clears them. With the backend they'll be
// saved per user in the database, and this shape is roughly what the database will store.

import type { Paper } from "./papers";
import type { Run } from "./types";
import type { Decisions } from "./review";

export type Thread = {
  id: string;
  title: string;
  autoTitle: boolean; // true until the researcher renames it; then the title stops following the papers
  properties: string;
  papers: Paper[];
  run: Run | null;
  decisions: Decisions;
  extractedWith: string | null; // fingerprint of the inputs used for the last run (see inputsKey)
};

// a change to one thread: either the new fields, or a function of the current thread
// (the function form always sees the LATEST thread, even when updates arrive quickly, like run progress)
export type ThreadPatch = Partial<Thread> | ((thread: Thread) => Partial<Thread>);

export function newThread(id: string): Thread {
  return { id, title: "New thread", autoTitle: true, properties: "", papers: [], run: null, decisions: {}, extractedWith: null };
}

// The default name follows the papers: "Inal_2017_Nat_Commun", or "Inal_2017_Nat_Commun + 2 more"
export function autoTitle(papers: Paper[]): string {
  if (papers.length === 0) return "New thread";
  const first = papers[0].file.name.replace(/\.pdf$/i, "");
  return papers.length === 1 ? first : `${first} + ${papers.length - 1} more`;
}

// A short fingerprint of what the run depends on: the properties and the exact papers.
// If it differs from extractedWith, the results on screen are out of date.
export function inputsKey(thread: Thread): string {
  return thread.properties.trim() + "|" + thread.papers.map((paper) => paper.id).join(",");
}

export function isStale(thread: Thread): boolean {
  return thread.run?.status === "done" && thread.extractedWith !== inputsKey(thread);
}

export function isEmpty(thread: Thread): boolean {
  return thread.papers.length === 0 && thread.run === null && thread.properties.trim() === "";
}

export function isRunning(thread: Thread): boolean {
  return thread.run !== null && (thread.run.status === "queued" || thread.run.status === "running");
}
