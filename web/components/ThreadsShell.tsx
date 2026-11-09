// components/ThreadsShell.tsx
// The app frame: the sidebar on the left, the active thread on the right.
// It OWNS every thread's data (properties, papers, run, decisions), so switching threads
// never loses anything, and a run keeps going while you look at another thread.

"use client";

import { useEffect, useRef, useState } from "react";
import type { Row } from "@/lib/types";
import { autoTitle, inputsKey, isEmpty, newThread, type Thread, type ThreadPatch } from "@/lib/threads";
import { startSampleRun } from "@/lib/sample-run";
import Sidebar from "./Sidebar";
import Workspace from "./Workspace";

export default function ThreadsShell({ sampleRows }: { sampleRows: Row[] }) {
  // STATE: all threads, which one is open, and a counter for new ids.
  // (A counter, not a random id: the first render happens on the server AND in the browser,
  // and a random id would differ between the two.)
  const [threads, setThreads] = useState<Thread[]>([newThread("t1")]);
  const [activeId, setActiveId] = useState("t1");
  const [nextNumber, setNextNumber] = useState(2);

  // the cancel function of each thread's running run, by thread id
  const cancels = useRef(new Map<string, () => void>());
  useEffect(() => {
    const running = cancels.current;
    return () => running.forEach((cancel) => cancel()); // leaving the page stops every run
  }, []);

  const active = threads.find((thread) => thread.id === activeId) ?? threads[0];

  function update(id: string, patch: ThreadPatch) {
    setThreads((current) =>
      current.map((thread) => (thread.id === id ? { ...thread, ...(typeof patch === "function" ? patch(thread) : patch) } : thread)),
    );
  }

  function addThread() {
    // don't pile up empty threads: if the open one is empty, just stay on it
    if (isEmpty(active)) return;
    const id = `t${nextNumber}`;
    setNextNumber(nextNumber + 1);
    setThreads([newThread(id), ...threads]); // newest on top
    setActiveId(id);
  }

  function deleteThread(id: string) {
    cancels.current.get(id)?.();
    cancels.current.delete(id);
    const remaining = threads.filter((thread) => thread.id !== id);
    if (remaining.length === 0) {
      // never leave the app with no thread at all
      const fresh = newThread(`t${nextNumber}`);
      setNextNumber(nextNumber + 1);
      setThreads([fresh]);
      setActiveId(fresh.id);
      return;
    }
    setThreads(remaining);
    if (id === activeId) setActiveId(remaining[0].id);
  }

  function extract(thread: Thread) {
    cancels.current.get(thread.id)?.(); // a new Extract replaces this thread's previous run
    update(thread.id, { decisions: {}, extractedWith: inputsKey(thread) }); // new results = a fresh review
    // PROTOTYPE: fake progress, then the sample rows. Later: send the papers + properties to the backend.
    const cancel = startSampleRun(thread.papers, sampleRows, (run) => update(thread.id, { run }));
    cancels.current.set(thread.id, cancel);
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar
        threads={threads}
        activeId={active.id}
        onSelect={setActiveId}
        onNew={addThread}
        onRename={(id, title) => update(id, { title, autoTitle: false })}
        onDelete={deleteThread}
      />
      <main className="min-w-0 flex-1 md:h-screen md:overflow-y-auto">
        <div className="mx-auto w-full max-w-7xl px-6 py-10">
          <p className="text-sm text-soft">Prototype · results use sample data until the backend exists</p>
          <h1 className="mb-8 truncate text-2xl font-semibold tracking-tight text-ink">{active.title}</h1>
          <Workspace
            // key: a different thread = a fresh Workspace, so things like the review queue
            // or the selected row never leak from one thread into another
            key={active.id}
            thread={active}
            onChange={(patch) => update(active.id, patch)}
            onPapersChange={(papers) =>
              update(active.id, (thread) => ({ papers, title: thread.autoTitle ? autoTitle(papers) : thread.title }))
            }
            onExtract={() => extract(active)}
          />
        </div>
      </main>
    </div>
  );
}
