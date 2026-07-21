"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { type PatientLanguage, patientText } from "../../../lib/patient-i18n";

interface ConversationMessage {
  message_id: string;
  direction: "inbound" | "outbound";
  content: string;
  message_type: "patient" | "system" | "care_team";
  delivery_status: string;
  created_at: string;
}

interface PendingSubmission {
  id: string;
  candidate_payload: {
    systolic: number;
    diastolic: number;
    measured_at: string;
    medication_taken: string;
    missed_medication_reason_code?: string | null;
    context_codes: string[];
  };
}

interface ConversationState {
  channel_label: string;
  preferred_language: PatientLanguage;
  real_whatsapp_configured: boolean;
  messages: ConversationMessage[];
  pending_submission: PendingSubmission | null;
}

export default function ConversationPage() {
  const [conversation, setConversation] = useState<ConversationState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/patient/conversation", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Unable to load conversation.");
        return body as ConversationState;
      })
      .then((body) => { if (active) setConversation(body); })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load conversation.");
      });
    return () => { active = false; };
  }, []);

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const message = String(form.get("message") ?? "").trim();
    if (!message) return;
    setBusy(true); setError(null);
    try {
      const response = await fetch("/api/patient/conversation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Unable to send message.");
      setConversation(body.conversation);
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to send message.");
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "confirm" | "cancel", refocus = false) {
    const pending = conversation?.pending_submission;
    if (!pending) return;
    setBusy(true); setError(null);
    try {
      const response = await fetch(
        `/api/patient/conversation/${pending.id}/${action}`,
        { method: "POST" },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Unable to complete action.");
      setConversation(body.conversation);
      if (refocus) window.setTimeout(() => inputRef.current?.focus(), 0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to complete action.");
    } finally {
      setBusy(false);
    }
  }

  const pending = conversation?.pending_submission;
  const text = patientText(conversation?.preferred_language);
  return (
    <div className="min-h-screen bg-[#e7edea] text-slate-950">
      <header className="bg-[#075e54] text-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <div>
            <Link className="text-sm font-semibold no-underline" href="/patient">← {text.back}</Link>
            <h1 className="mb-0 mt-1 text-lg font-semibold">{text.title}</h1>
          </div>
          <span className="rounded-full bg-white/15 px-3 py-1 text-xs">
            {conversation?.real_whatsapp_configured ? "Meta test connected" : "Simulator"}
          </span>
        </div>
      </header>
      <main className="mx-auto flex min-h-[calc(100vh-76px)] max-w-3xl flex-col bg-[#f6f1e8] shadow-sm">
        <section className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-950">
          <strong>{conversation?.channel_label ?? "WhatsApp-compatible simulator"}.</strong>{" "}
          {text.safety}
        </section>
        {error ? <p aria-live="assertive" className="m-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p> : null}
        <section aria-label="Conversation history" className="flex flex-1 flex-col gap-3 overflow-y-auto p-4 sm:p-6">
          {conversation?.messages.length ? conversation.messages.map((message) => (
            <article
              className={`max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${
                message.message_type === "patient"
                  ? "ml-auto rounded-br-sm bg-[#d9fdd3]"
                  : message.message_type === "care_team"
                    ? "mr-auto rounded-bl-sm border border-emerald-200 bg-emerald-50"
                    : "mr-auto rounded-bl-sm bg-white"
              }`}
              key={message.message_id}
            >
              <p className="m-0 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                {message.message_type === "patient" ? text.you : message.message_type === "care_team" ? text.careTeam : text.template}
              </p>
              <p className="mb-0 mt-1 whitespace-pre-wrap">{message.content}</p>
            </article>
          )) : <div className="m-auto max-w-md rounded-2xl bg-white p-5 text-center shadow-sm"><h2 className="m-0 text-lg font-semibold">{text.emptyTitle}</h2><p className="mb-0 mt-2 text-sm leading-6 text-slate-600">{text.emptyHelp}</p></div>}
          {pending ? <section aria-labelledby="extraction-heading" className="rounded-2xl border-2 border-[#25d366] bg-white p-5 shadow-sm"><p className="m-0 text-xs font-semibold uppercase tracking-wide text-[#08766b]">{text.draft}</p><h2 className="mb-0 mt-2 text-lg font-semibold" id="extraction-heading">{text.check}</h2><p className="mb-0 mt-4 text-3xl font-semibold">{pending.candidate_payload.systolic} / {pending.candidate_payload.diastolic}</p><dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2"><div><dt className="font-semibold">{text.measured}</dt><dd className="m-0 text-slate-600">{new Date(pending.candidate_payload.measured_at).toLocaleString()}</dd></div><div><dt className="font-semibold">{text.medication}</dt><dd className="m-0 capitalize text-slate-600">{pending.candidate_payload.medication_taken.replaceAll("_", " ")}</dd></div></dl><div className="mt-5 flex flex-wrap gap-2"><button className="rounded-lg bg-[#075e54] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} onClick={() => void act("confirm")} type="button">{text.confirm}</button><button className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold disabled:opacity-50" disabled={busy} onClick={() => void act("cancel", true)} type="button">{text.correct}</button><button className="px-3 py-2.5 text-sm font-semibold text-slate-600 disabled:opacity-50" disabled={busy} onClick={() => void act("cancel")} type="button">{text.cancel}</button></div></section> : null}
        </section>
        <form className="flex gap-2 border-t border-slate-200 bg-white p-3 sm:p-4" onSubmit={sendMessage}>
          <label className="sr-only" htmlFor="conversation-message">{text.message}</label>
          <input className="min-h-12 flex-1 rounded-full border border-slate-300 px-4 text-sm" disabled={busy} id="conversation-message" name="message" placeholder={pending ? text.pendingPlaceholder : text.placeholder} ref={inputRef} required />
          <button className="min-h-12 rounded-full bg-[#25d366] px-5 text-sm font-semibold text-[#063f3a] disabled:opacity-50" disabled={busy} type="submit">{text.send}</button>
        </form>
      </main>
    </div>
  );
}
