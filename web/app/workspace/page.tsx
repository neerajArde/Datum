// app/app/page.tsx
// The workspace page, at the URL "/app".
// No "use client": this is a SERVER component. It runs on the server, builds the HTML,
// and hands the rows to ResultsTable, which takes over in the browser.

import ResultsTable from "@/components/ResultsTable";
import { sampleRows } from "@/lib/sample-rows";

export default function WorkspacePage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-6 py-10">
      <p className="text-sm text-zinc-500">Sample run · 1 paper</p>
      <h1 className="mb-8 text-2xl font-semibold tracking-tight text-zinc-900">
        Inal_2017_Nat_Commun
      </h1>
      {/* the rows go in as a PROP */}
      <ResultsTable rows={sampleRows} />
    </main>
  );
}
