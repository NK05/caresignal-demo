import Link from "next/link";

const principles = [
  "Synthetic demonstration data only",
  "Deterministic rules own review priority",
  "GPT-5.6 supports language and workflow",
  "Clinicians approve patient-facing drafts",
];

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8 sm:px-10 lg:px-16">
      <header className="flex items-center justify-between border-b border-[var(--border)] pb-5">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-[var(--primary)] text-lg font-bold text-white">
            C
          </span>
          <div>
            <p className="m-0 text-lg font-semibold">CareSignal</p>
            <p className="m-0 text-xs text-[var(--muted)]">OpenAI Build Week prototype</p>
          </div>
        </div>
        <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--muted)]">
          Foundation online
        </span>
      </header>

      <section className="grid flex-1 items-center gap-12 py-16 lg:grid-cols-[1.15fr_0.85fr]">
        <div>
          <p className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-[var(--primary)]">
            English · Shona · Ndebele
          </p>
          <h1 className="m-0 max-w-3xl text-4xl font-semibold leading-tight tracking-[-0.035em] sm:text-6xl">
            From a home BP message to accountable clinical follow-up.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[var(--muted)]">
            CareSignal helps adults already receiving hypertension treatment share confirmed readings through a
            lightweight app or WhatsApp-compatible channel, while care teams own every follow-up task through
            resolution.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="rounded-lg bg-[var(--primary)] px-5 py-3 text-sm font-semibold text-white" href="/patient">
              Open patient experience
            </Link>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-5 py-3 text-sm font-semibold text-[var(--primary)] transition-colors hover:bg-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]" href="/clinician">
              Open clinician workspace
            </Link>
          </div>
        </div>

        <aside className="rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-7 shadow-[0_24px_80px_rgba(17,38,58,0.08)]">
          <p className="m-0 text-sm font-semibold text-[var(--primary)]">Locked safety boundary</p>
          <h2 className="mb-6 mt-2 text-2xl font-semibold">A workflow prototype—not a diagnostic tool.</h2>
          <ul className="m-0 grid list-none gap-3 p-0">
            {principles.map((principle) => (
              <li key={principle} className="flex gap-3 rounded-xl bg-[var(--accent)] px-4 py-3 text-sm leading-6">
                <span aria-hidden="true" className="font-bold text-[var(--primary)]">
                  ✓
                </span>
                {principle}
              </li>
            ))}
          </ul>
        </aside>
      </section>

      <footer className="border-t border-[var(--border)] py-5 text-xs leading-5 text-[var(--muted)]">
        CareSignal does not diagnose conditions, recommend medication changes, replace a healthcare professional,
        or provide emergency services.
      </footer>
    </main>
  );
}
