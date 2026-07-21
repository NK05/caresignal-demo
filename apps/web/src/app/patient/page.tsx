"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

interface HomeData {
  profile: { display_name: string; synthetic_identifier: string; preferred_language: string };
  readings: Array<{ id: string; systolic: number; diastolic: number; measured_at: string }>;
  follow_up: { status: string; message: string; latest_care_message: { content: string; sent_at: string } | null };
}

interface PendingSubmission {
  id: string;
  candidate_payload: { systolic: number; diastolic: number; measured_at: string; medication_taken: string; context_codes: string[] };
}

export default function PatientPage() {
  const [home, setHome] = useState<HomeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [pending, setPending] = useState<PendingSubmission | null>(null);
  const [busy, setBusy] = useState(false);
  const [acknowledgement, setAcknowledgement] = useState<string | null>(null);

  async function loadHome() {
    setError(null);
    try {
      const response = await fetch("/api/patient/home", { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Unable to load patient workspace.");
      setHome(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load patient workspace.");
    }
  }

  useEffect(() => {
    let active = true;
    fetch("/api/patient/home", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Unable to load patient workspace.");
        return body as HomeData;
      })
      .then((body) => { if (active) setHome(body); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Unable to load patient workspace."); });
    return () => { active = false; };
  }, []);

  async function submitReading(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(null);
    const form = new FormData(event.currentTarget);
    const measured = String(form.get("measured_at"));
    const payload = {
      systolic: Number(form.get("systolic")), diastolic: Number(form.get("diastolic")),
      measured_at: new Date(measured).toISOString(), medication_taken: form.get("medication_taken"),
      context_codes: form.get("rested") ? ["rested"] : [], note: null,
    };
    try {
      const response = await fetch("/api/patient/submissions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const body = await response.json();
      if (!response.ok) throw new Error(Array.isArray(body.detail) ? "Check the reading details and try again." : body.detail);
      setPending(body); setShowForm(false);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save reading."); }
    finally { setBusy(false); }
  }

  async function finish(action: "confirm" | "reject") {
    if (!pending) return;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`/api/patient/submissions/${pending.id}/${action}`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Unable to complete confirmation.");
      setAcknowledgement(action === "confirm" ? body.acknowledgement : "Reading cancelled. Nothing was added to your history.");
      setPending(null); await loadHome();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to complete confirmation."); }
    finally { setBusy(false); }
  }

  const latest = home?.readings[0];
  return (
    <div className="min-h-screen bg-[#f4f7f9] text-slate-950">
      <header className="bg-[#063f3a] text-white"><div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6"><Link className="font-semibold no-underline" href="/">CareSignal</Link><span className="rounded-full border border-white/20 px-3 py-1 text-xs">Synthetic patient demo</span></div></header>
      <main className="mx-auto max-w-5xl px-4 py-7 sm:px-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-[#08766b]">Patient home · English</p><h1 className="mb-0 mt-2 text-3xl font-semibold">Hello, {home?.profile.display_name ?? "patient"}</h1><p className="mb-0 mt-2 text-sm text-slate-500">{home?.profile.synthetic_identifier} · Fictional identity</p></div><div className="flex flex-wrap gap-2"><Link className="rounded-xl border border-[#075e54] bg-white px-5 py-3 text-sm font-semibold text-[#075e54] no-underline" href="/patient/conversation">Conversation demo</Link><button className="rounded-xl bg-[#075e54] px-5 py-3 text-sm font-semibold text-white" onClick={() => { setShowForm(true); setAcknowledgement(null); }} type="button">Record blood pressure</button></div></div>
        {error ? <p aria-live="assertive" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
        {acknowledgement ? <p aria-live="polite" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-900">{acknowledgement}</p> : null}
        {showForm ? <form className="mt-5 grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2" onSubmit={submitReading}><h2 className="m-0 text-xl font-semibold sm:col-span-2">Record a confirmed home reading</h2><label className="grid gap-1 text-sm font-medium">Systolic<input className="min-h-12 rounded-lg border border-slate-300 px-3" max="300" min="40" name="systolic" required type="number" /></label><label className="grid gap-1 text-sm font-medium">Diastolic<input className="min-h-12 rounded-lg border border-slate-300 px-3" max="200" min="30" name="diastolic" required type="number" /></label><label className="grid gap-1 text-sm font-medium">Measurement time<input className="min-h-12 rounded-lg border border-slate-300 px-3" name="measured_at" required type="datetime-local" /></label><label className="grid gap-1 text-sm font-medium">Did you take your medication?<select className="min-h-12 rounded-lg border border-slate-300 px-3" name="medication_taken"><option value="yes">Yes</option><option value="no">No</option><option value="prefer_not_to_say">Prefer not to say</option></select></label><label className="flex items-center gap-2 text-sm sm:col-span-2"><input name="rested" type="checkbox" /> I was resting when I measured</label><div className="flex gap-3 sm:col-span-2"><button className="rounded-lg bg-[#075e54] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Review reading</button><button className="px-4 text-sm font-semibold text-slate-600" onClick={() => setShowForm(false)} type="button">Cancel</button></div></form> : null}
        {pending ? <section aria-labelledby="confirm-heading" className="mt-5 rounded-2xl border border-amber-200 bg-white p-5 shadow-sm"><p className="m-0 text-xs font-semibold uppercase text-amber-800">Not yet recorded</p><h2 className="mb-0 mt-2 text-xl font-semibold" id="confirm-heading">Confirm this reading</h2><p className="mb-0 mt-4 text-3xl font-semibold">{pending.candidate_payload.systolic} / {pending.candidate_payload.diastolic}</p><p className="mb-0 mt-2 text-sm text-slate-600">Measured {new Date(pending.candidate_payload.measured_at).toLocaleString()} · Medication: {pending.candidate_payload.medication_taken}</p><div className="mt-5 flex flex-wrap gap-3"><button className="rounded-lg bg-[#075e54] px-5 py-3 text-sm font-semibold text-white" disabled={busy} onClick={() => void finish("confirm")} type="button">Confirm and save</button><button className="rounded-lg border border-slate-300 px-5 py-3 text-sm font-semibold" disabled={busy} onClick={() => void finish("reject")} type="button">Reject reading</button></div></section> : null}
        <div className="mt-6 grid gap-5 md:grid-cols-2"><section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="m-0 text-lg font-semibold">Current follow-up</h2><p className="mb-0 mt-3 text-sm leading-6 text-slate-700">{home?.follow_up.message ?? "Loading…"}</p>{home?.follow_up.latest_care_message ? <div className="mt-4 rounded-xl bg-emerald-50 p-4"><p className="m-0 text-xs font-semibold text-emerald-800">Care-team message</p><p className="mb-0 mt-2 text-sm leading-6">{home.follow_up.latest_care_message.content}</p></div> : null}</section><section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="m-0 text-lg font-semibold">Latest confirmed reading</h2>{latest ? <><p className="mb-0 mt-3 text-3xl font-semibold">{latest.systolic} / {latest.diastolic}</p><p className="mb-0 mt-2 text-xs text-slate-500">{new Date(latest.measured_at).toLocaleString()}</p></> : <p className="text-sm text-slate-500">No confirmed readings.</p>}</section></div>
        <p className="mx-auto mt-6 max-w-3xl text-center text-xs leading-5 text-slate-500">CareSignal does not diagnose conditions, replace a healthcare professional, recommend medication changes, or provide emergency services. In a real emergency, contact local emergency services.</p>
      </main>
    </div>
  );
}
