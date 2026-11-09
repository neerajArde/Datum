// lib/papers.ts
// Helpers for the papers a researcher adds in the composer. Plain logic, no UI.

// A paper waiting to be extracted. `file` is the actual PDF, kept in the browser's memory
// until the backend exists to receive it.
export type Paper = {
  id: string;
  file: File;
};

export const MAX_PAPER_BYTES = 50 * 1024 * 1024; // 50 MB, same limit as the old app

// "1.2 MB", "507 KB"
export function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function isPdf(file: File): boolean {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

// Adds newly chosen files to the list. Skips anything that isn't a PDF or is too big,
// and replaces a paper with the same name instead of adding a duplicate.
// Returns the new list plus a plain-English note for every file that was skipped.
export function addPapers(current: Paper[], files: File[]): { papers: Paper[]; skipped: string[] } {
  const papers = [...current];
  const skipped: string[] = [];
  for (const file of files) {
    if (!isPdf(file)) {
      skipped.push(`${file.name} isn't a PDF`);
      continue;
    }
    if (file.size > MAX_PAPER_BYTES) {
      skipped.push(`${file.name} is over 50 MB`);
      continue;
    }
    const paper = { id: `${file.name}-${file.size}-${file.lastModified}`, file };
    const sameName = papers.findIndex((p) => p.file.name === file.name);
    if (sameName >= 0) papers[sameName] = paper;
    else papers.push(paper);
  }
  return { papers, skipped };
}
