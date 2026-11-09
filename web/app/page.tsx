// app/page.tsx
// The landing page, at "/". A server component: no interactivity, so it's sent as finished HTML
// (fast to load, and readable by LinkedIn link previews and search engines).
// Simple on purpose: the full visual redesign comes before launch.
// Every claim on this page is something Datum really does, with real numbers from real runs.

import Link from "next/link";
import { buttonStyles } from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import StatusBadge from "@/components/StatusBadge";

const STEPS = [
  { name: "Ingest", text: "Reads the text of every page of every PDF you add." },
  { name: "Filter", text: "Keeps only the parts that mention the properties you asked for." },
  { name: "Extract", text: "An AI pulls out each value with its material, unit, page and exact quote." },
  { name: "Verify", text: "Plain code, not AI, checks every value against the PDF itself." },
  { name: "Assemble", text: "One table: each value marked verified, to review, or flagged." },
];

const STATUSES = [
  { status: "verified" as const, text: "Found exactly where the AI said, in the paper. Accepted automatically." },
  { status: "review" as const, text: "Probably right, but something deserves a glance, and Datum says what." },
  { status: "flagged" as const, text: "Couldn't be matched to the paper. Left out of your download." },
];

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <span className="text-lg font-bold tracking-tight text-ink">
          Datum<span className="ml-0.5 inline-block h-2 w-2 rounded-sm bg-highlight" />
        </span>
        <nav className="flex items-center gap-5 text-sm">
          <a href="#how" className="text-muted hover:text-ink">
            How it works
          </a>
          <a href="https://github.com/neerajArde/datum" className="text-muted hover:text-ink">
            GitHub
          </a>
          <Link href="/workspace" className={buttonStyles("primary", "md")}>
            Open Datum
          </Link>
        </nav>
      </header>

      <main className="mx-auto max-w-5xl px-6">
        {/* hero */}
        <section className="py-20 text-center">
          <h1 className="mx-auto max-w-3xl text-5xl font-bold tracking-tight text-ink sm:text-6xl">
            Every number, traced to its page.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted">
            Datum turns research papers into a dataset. An AI reads the papers; plain code checks every value against
            the PDF, so you only look at the numbers that actually need a human.
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <Link href="/workspace" className={buttonStyles("primary", "lg")}>
              Open Datum
            </Link>
            <a href="#how" className={buttonStyles("secondary", "lg")}>
              See how it works
            </a>
          </div>
        </section>

        {/* a real receipt, from a real run on Inal et al. 2017 */}
        <Card as="section" className="mx-auto max-w-3xl p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm text-soft">PEDOT:PSS + EG · [μC*]OECT</p>
              <p className="text-3xl font-semibold tracking-tight text-ink">
                47 <span className="text-muted">± 6</span>{" "}
                <span className="text-base font-normal text-soft">F cm⁻¹ V⁻¹ s⁻¹</span>
              </p>
            </div>
            <StatusBadge status="verified" />
          </div>
          <div className="mt-4 rounded-lg border border-line bg-subtle p-1">
            <p className="px-3 pt-2 text-xs text-soft">Table 1, page 4 of Inal et al., Nature Communications 2017</p>
            <p className="m-2 rounded bg-surface p-4 font-mono text-sm text-body shadow-sm">
              PEDOT:PSS + EG19 &nbsp;39 ± 3 &nbsp;1.9 ± 1.3 &nbsp;75 ± 51 &nbsp;
              <mark className="rounded bg-highlight px-0.5 text-ink">47</mark> ± 6
            </p>
          </div>
          <p className="mt-3 text-sm text-muted">
            Checked in plain code: the value sits in this row, the closest material name before it is PEDOT:PSS + EG,
            and the unit fits μC*.
          </p>
        </Card>

        {/* how it works */}
        <section id="how" className="scroll-mt-8 py-20">
          <h2 className="text-3xl font-bold tracking-tight text-ink">The AI reads. The code checks.</h2>
          <p className="mt-3 max-w-2xl text-muted">
            Language models are fast readers that sometimes invent numbers. So Datum never trusts a value just because
            an AI produced it.
          </p>
          <ol className="mt-10 grid gap-4 sm:grid-cols-5">
            {STEPS.map((step, index) => (
              <li key={step.name}>
                <Card className="h-full p-4">
                  <p className="text-xs text-faint">{index + 1}</p>
                  <p className="font-semibold text-ink">{step.name}</p>
                  <p className="mt-1 text-sm text-muted">{step.text}</p>
                </Card>
              </li>
            ))}
          </ol>

          <div className="mt-12 grid gap-4 sm:grid-cols-3">
            {STATUSES.map((item) => (
              <Card key={item.status} className="p-5">
                <StatusBadge status={item.status} />
                <p className="mt-3 text-sm text-muted">{item.text}</p>
              </Card>
            ))}
          </div>
        </section>

        {/* the honest numbers */}
        <section className="border-t border-line py-16">
          <div className="grid gap-8 sm:grid-cols-3">
            <div>
              <p className="text-4xl font-bold text-ink">10 / 10</p>
              <p className="mt-1 text-sm text-muted">hand-checked benchmark values found in Inal et al. 2017</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-ink">5 engines</p>
              <p className="mt-1 text-sm text-muted">Cerebras, Groq, Gemini, Claude and OpenAI behind one router</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-ink">1 click</p>
              <p className="mt-1 text-sm text-muted">to a CSV of verified values, each with its page and quote</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-5xl flex-wrap justify-between gap-2 px-6 py-6 text-sm text-soft">
          <span>Built at HackPSU Fall 2026 by Team Ground Truth</span>
          <a href="https://github.com/neerajArde/datum" className="hover:text-ink">
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}
