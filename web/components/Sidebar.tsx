// components/Sidebar.tsx
// The thread list: the Datum mark, "New thread", and every thread with rename and delete.
// It holds no thread data itself; it shows what it's given and reports clicks up.

"use client";

import Link from "next/link";
import { useState } from "react";
import { isRunning, type Thread } from "@/lib/threads";
import Button from "./ui/Button";

type Props = {
  threads: Thread[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
};

export default function Sidebar({ threads, activeId, onSelect, onNew, onRename, onDelete }: Props) {
  return (
    <nav aria-label="Threads" className="flex flex-col gap-4 border-b border-line bg-surface p-4 md:h-screen md:w-64 md:shrink-0 md:border-r md:border-b-0">
      <Link href="/" className="px-2 text-lg font-bold tracking-tight text-ink">
        Datum<span className="ml-0.5 inline-block h-2 w-2 rounded-sm bg-highlight" />
      </Link>

      <Button variant="secondary" onClick={onNew} className="w-full text-left">
        + New thread
      </Button>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <p className="px-2 pb-1 text-xs text-faint">Threads</p>
        <ul className="space-y-0.5">
          {threads.map((thread) => (
            <ThreadItem
              // key = thread id, so each item keeps its own menu / rename state
              key={thread.id}
              thread={thread}
              active={thread.id === activeId}
              onSelect={() => onSelect(thread.id)}
              onRename={(title) => onRename(thread.id, title)}
              onDelete={() => onDelete(thread.id)}
            />
          ))}
        </ul>
      </div>

      <p className="px-2 text-xs text-faint">Prototype: threads reset on refresh until accounts exist.</p>
    </nav>
  );
}

// one row in the list, with its own small menu
function ThreadItem(props: {
  thread: Thread;
  active: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const { thread, active } = props;
  // STATE: is the ⋯ menu open, are we renaming, and is delete waiting for confirmation?
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(thread.title);
  const [confirmDelete, setConfirmDelete] = useState(false);

  function saveRename() {
    if (draft.trim() !== "") props.onRename(draft.trim());
    setRenaming(false);
  }

  // a short line under the title saying what state the thread is in
  const subtitle = isRunning(thread)
    ? "Extracting…"
    : thread.run?.status === "done"
      ? `${thread.run.rows.length} values`
      : thread.papers.length > 0
        ? `${thread.papers.length} ${thread.papers.length === 1 ? "paper" : "papers"}`
        : "Empty";

  if (renaming) {
    return (
      <li className="px-1">
        <input
          autoFocus
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={saveRename}
          onKeyDown={(event) => {
            if (event.key === "Enter") saveRename();
            if (event.key === "Escape") setRenaming(false);
          }}
          aria-label="Thread name"
          maxLength={60}
          className="w-full rounded-md border border-line-strong bg-surface px-2 py-1.5 text-sm text-ink focus:outline-none"
        />
      </li>
    );
  }

  return (
    <li>
      <div className={`group flex items-center rounded-md ${active ? "bg-subtle-strong" : "hover:bg-subtle"}`}>
        <button
          type="button"
          onClick={props.onSelect}
          aria-current={active ? "page" : undefined}
          className="min-w-0 flex-1 px-2 py-1.5 text-left"
        >
          <span className="block truncate text-sm text-ink">{thread.title}</span>
          <span className="flex items-center gap-1.5 text-xs text-soft">
            {isRunning(thread) && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink motion-reduce:animate-none" />}
            {subtitle}
          </span>
        </button>
        <button
          type="button"
          onClick={() => {
            setMenuOpen(!menuOpen);
            setConfirmDelete(false);
          }}
          aria-label={`Options for ${thread.title}`}
          aria-expanded={menuOpen}
          className="mr-1 rounded px-1.5 text-soft hover:bg-line-soft hover:text-ink"
        >
          ⋯
        </button>
      </div>

      {menuOpen && (
        <div className="mt-1 mb-2 flex gap-1 px-2">
          <Button
            variant="ghost"
            onClick={() => {
              setDraft(thread.title);
              setRenaming(true);
              setMenuOpen(false);
            }}
          >
            Rename
          </Button>
          {/* deleting can't be undone in the prototype, so it asks once more */}
          {confirmDelete ? (
            <Button variant="ghost" onClick={props.onDelete} className="text-flagged-ink hover:text-flagged-ink">
              Yes, delete
            </Button>
          ) : (
            <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
              Delete
            </Button>
          )}
        </div>
      )}
    </li>
  );
}
