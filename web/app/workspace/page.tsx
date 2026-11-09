// app/workspace/page.tsx
// The workspace page, at the URL "/workspace".
// No "use client": this is a SERVER component. It builds the HTML on the server
// and hands the rows to Workspace, which takes over in the browser.

import Workspace from "@/components/Workspace";
import { demoRows, sampleRows } from "@/lib/sample-rows";

export default function WorkspacePage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-6 py-10">
      <p className="text-sm text-soft">Prototype · results use sample data until the backend exists</p>
      <h1 className="mb-8 text-2xl font-semibold tracking-tight text-ink">Demo thread</h1>
      {/* the rows go in as a PROP */}
      <Workspace sampleRows={[...sampleRows, ...demoRows]} />
    </main>
  );
}
