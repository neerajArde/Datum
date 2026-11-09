// app/workspace/page.tsx
// The app, at the URL "/workspace".
// No "use client": this is a SERVER component. It hands the sample rows to ThreadsShell,
// which runs the whole app in the browser.

import ThreadsShell from "@/components/ThreadsShell";
import { demoRows, sampleRows } from "@/lib/sample-rows";

export default function WorkspacePage() {
  return <ThreadsShell sampleRows={[...sampleRows, ...demoRows]} />;
}
