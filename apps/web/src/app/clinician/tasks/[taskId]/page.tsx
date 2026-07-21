"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import type {
  ClinicianTaskDetailData,
  MedicationStatus,
  TaskPriority,
  TaskStatus,
} from "@/lib/clinician";

const priorityLabels: Record<TaskPriority, string> = {
  urgent_review: "Urgent review",
  needs_review: "Needs review",
  watch: "Watch",
  routine: "Routine",
};

const priorityStyles: Record<TaskPriority, string> = {
  urgent_review: "border-rose-200 bg-rose-50 text-rose-800",
  needs_review: "border-amber-200 bg-amber-50 text-amber-900",
  watch: "border-sky-200 bg-sky-50 text-sky-900",
  routine: "border-slate-200 bg-slate-50 text-slate-700",
};

const statusLabels: Record<TaskStatus, string> = {
  open: "Open",
  assigned: "Assigned",
  in_review: "In review",
  resolved: "Resolved",
};

const medicationLabels: Record<MedicationStatus, string> = {
  yes: "Reported taken",
  no: "Reported missed",
  unknown: "Unknown",
  prefer_not_to_say: "Preferred not to say",
};

const languageLabels = {
  en: "English",
  sn: "Shona",
  nd: "Ndebele",
  mixed: "Mixed",
  unknown: "Unknown",
};

const channelLabels = {
  app: "CareSignal app",
  whatsapp_simulator: "WhatsApp simulator",
  whatsapp_sandbox: "WhatsApp sandbox",
};

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-ZW", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function LoadingTask() {
  return (
    <div aria-live="polite" className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]" role="status">
      <span className="sr-only">Loading clinician task</span>
      <div className="h-[38rem] animate-pulse rounded-2xl border border-slate-200 bg-white" />
      <div className="h-[30rem] animate-pulse rounded-2xl border border-slate-200 bg-white" />
    </div>
  );
}

interface GroundedCaseBrief {
  summary: string;
  timeline_points: string[];
  rule_explanation: string;
  adherence_context: string | null;
  missing_information: string[];
  source_record_ids: string[];
  safety_note: string;
}

export default function ClinicianTaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const [data, setData] = useState<ClinicianTaskDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [requestKey, setRequestKey] = useState(0);
  const [ownerId, setOwnerId] = useState("");
  const [outcomeCode, setOutcomeCode] = useState("review_completed");
  const [outcomeNote, setOutcomeNote] = useState("");
  const [reopenReason, setReopenReason] = useState("");
  const [contactOutcome, setContactOutcome] = useState("reached");
  const [contactNote, setContactNote] = useState("");
  const [messageLanguage, setMessageLanguage] = useState("en");
  const [messageContent, setMessageContent] = useState("");
  const [clinicianOutcome, setClinicianOutcome] = useState("");
  const [caseBrief, setCaseBrief] = useState<GroundedCaseBrief | null>(null);

  useEffect(() => {
    let active = true;
    async function loadTask() {
      setError(null);
      try {
        const response = await fetch(`/api/clinician/tasks/${encodeURIComponent(taskId)}`, {
          cache: "no-store",
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Unable to load this task.");
        if (active) {
          const detail = body as ClinicianTaskDetailData;
          setData(detail);
          setOwnerId(
            detail.task.assigned_owner?.clinician_id ?? detail.current_clinician.clinician_id,
          );
          setMessageLanguage(
            ["en", "sn", "nd"].includes(detail.task.preferred_language)
              ? detail.task.preferred_language
              : "en",
          );
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load this task.");
      }
    }
    void loadTask();
    return () => {
      active = false;
    };
  }, [requestKey, taskId]);

  async function runAction(action: string, body?: object) {
    setPendingAction(action);
    setActionError(null);
    try {
      const response = await fetch(
        `/api/clinician/tasks/${encodeURIComponent(taskId)}/${action}`,
        {
          method: "POST",
          headers: body ? { "Content-Type": "application/json" } : undefined,
          body: body ? JSON.stringify(body) : undefined,
        },
      );
      const responseBody = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(responseBody.detail)
          ? "Please check the required fields and try again."
          : responseBody.detail;
        throw new Error(detail ?? "The task action could not be completed.");
      }
      const detail = responseBody as ClinicianTaskDetailData;
      setData(detail);
      setOwnerId(
        detail.task.assigned_owner?.clinician_id ?? detail.current_clinician.clinician_id,
      );
      if (action === "resolve") setOutcomeNote("");
      if (action === "reopen") setReopenReason("");
      if (action === "contact-attempts") setContactNote("");
      if (action === "draft-message") setMessageContent("");
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "The task action failed.");
    } finally {
      setPendingAction(null);
    }
  }

  function submitAssignment(event: FormEvent) {
    event.preventDefault();
    void runAction("assign", { clinician_id: ownerId });
  }

  function submitResolution(event: FormEvent) {
    event.preventDefault();
    void runAction("resolve", {
      outcome_code: outcomeCode,
      outcome_note: outcomeNote.trim() || null,
    });
  }

  function submitReopen(event: FormEvent) {
    event.preventDefault();
    void runAction("reopen", { reason: reopenReason });
  }

  function submitContact(event: FormEvent) {
    event.preventDefault();
    if (!data) return;
    void runAction("contact-attempts", {
      channel: data.task.preferred_channel,
      outcome_code: contactOutcome,
      note: contactNote.trim() || null,
    });
  }

  function submitMessage(event: FormEvent) {
    event.preventDefault();
    void runAction("draft-message", {
      language: messageLanguage,
      content: messageContent,
    });
  }

  async function generateBrief() {
    setPendingAction("case-brief"); setActionError(null);
    try {
      const response = await fetch(`/api/clinician/tasks/${encodeURIComponent(taskId)}/case-brief`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "AI case brief is unavailable.");
      setCaseBrief(body as GroundedCaseBrief);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "AI case brief is unavailable.");
    } finally { setPendingAction(null); }
  }

  function generateAIDraft() {
    if (!clinicianOutcome.trim()) return;
    void runAction("ai-draft-message", { language: messageLanguage, clinician_outcome: clinicianOutcome.trim() });
  }

  return (
    <div className="min-h-screen bg-[#f4f7f9] text-slate-950">
      <header className="border-b border-emerald-950/10 bg-[#063f3a] text-white">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-4 py-3 sm:px-6 lg:px-9">
          <Link className="flex items-center gap-2 font-semibold no-underline" href="/">
            <span className="grid size-8 place-items-center rounded-lg bg-white text-sm font-bold text-[#075e54]">C</span>
            CareSignal
          </Link>
          <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[11px]">Synthetic clinic</span>
        </div>
      </header>

      <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-9 lg:py-8">
        <Link className="inline-flex items-center gap-2 text-sm font-semibold text-[#08766b] underline-offset-4 hover:underline" href="/clinician">
          <span aria-hidden="true">←</span> Back to review queue
        </Link>

        <div className="mb-6 mt-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#08766b]">Clinician task</p>
            <h1 className="m-0 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
              {data?.task.patient_synthetic_identifier ?? "Review detail"}
            </h1>
            {data ? <p className="mb-0 mt-2 text-sm text-slate-600">{data.task.patient_display_name} · Fictional patient</p> : null}
          </div>
          {data ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${priorityStyles[data.task.priority]}`}>{priorityLabels[data.task.priority]}</span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700">{statusLabels[data.task.status]}</span>
              {data.task.overdue ? <span className="rounded-full bg-rose-100 px-3 py-1.5 text-xs font-semibold text-rose-800">Overdue</span> : null}
            </div>
          ) : null}
        </div>

        {error ? (
          <section aria-live="assertive" className="rounded-2xl border border-rose-200 bg-white p-6 shadow-sm">
            <h2 className="m-0 text-lg font-semibold text-rose-900">Task unavailable</h2>
            <p className="mb-0 mt-2 text-sm text-slate-600">{error}</p>
            <button className="mt-4 rounded-lg bg-[#075e54] px-4 py-2 text-sm font-semibold text-white" onClick={() => setRequestKey((key) => key + 1)} type="button">Try again</button>
          </section>
        ) : !data ? (
          <LoadingTask />
        ) : (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
            <div className="space-y-5">
              <section aria-labelledby="marker-heading" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_34px_rgba(15,23,42,0.04)] sm:p-6">
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                  <div className="max-w-3xl">
                    <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Deterministic marker</p>
                    <h2 className="mb-0 mt-2 text-xl font-semibold" id="marker-heading">{data.task.flag_title}</h2>
                    <p className="mb-0 mt-3 text-sm leading-6 text-slate-700">{data.task.flag_reason}</p>
                  </div>
                  <div className="min-w-40 rounded-xl bg-slate-50 p-4">
                    <p className="m-0 text-xs text-slate-500">Latest confirmed BP</p>
                    <p className="mb-0 mt-1 text-3xl font-semibold tracking-[-0.04em]">{data.task.latest_reading.systolic}<span className="mx-1 text-slate-300">/</span>{data.task.latest_reading.diastolic}</p>
                    <p className="mb-0 mt-1 text-xs text-slate-500">{formatTimestamp(data.task.latest_reading.measured_at)}</p>
                  </div>
                </div>
                <dl className="mt-5 grid gap-3 border-t border-slate-200 pt-5 text-sm sm:grid-cols-3">
                  <div><dt className="text-xs text-slate-500">Language</dt><dd className="m-0 mt-1 font-medium">{languageLabels[data.task.preferred_language]}</dd></div>
                  <div><dt className="text-xs text-slate-500">Patient channel</dt><dd className="m-0 mt-1 font-medium">{channelLabels[data.task.preferred_channel]}</dd></div>
                  <div><dt className="text-xs text-slate-500">Rule version</dt><dd className="m-0 mt-1 font-mono text-xs font-medium">{data.task.rule_version}</dd></div>
                </dl>
              </section>

              <section aria-labelledby="evidence-heading" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_34px_rgba(15,23,42,0.04)] sm:p-6">
                <h2 className="m-0 text-lg font-semibold" id="evidence-heading">Rule evidence</h2>
                <p className="mb-0 mt-1 text-xs text-slate-500">Versioned, prompt-independent reasons linked to confirmed readings.</p>
                <ol className="mb-0 mt-5 list-none space-y-4 p-0">
                  {data.evidence.map((evidence) => (
                    <li className="rounded-xl border border-slate-200 p-4" key={evidence.rule_evaluation_id}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="m-0 font-semibold">{evidence.title}</p>
                        <span className="rounded-full bg-slate-100 px-2 py-1 font-mono text-[10px] text-slate-600">{evidence.rule_version}</span>
                      </div>
                      <p className="mb-0 mt-2 text-sm leading-6 text-slate-700">{evidence.reason}</p>
                      <p className="mb-0 mt-3 text-xs leading-5 text-slate-500">Source: {evidence.source_reference}</p>
                    </li>
                  ))}
                </ol>
              </section>

              <section aria-labelledby="readings-heading" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_34px_rgba(15,23,42,0.04)] sm:p-6">
                <h2 className="m-0 text-lg font-semibold" id="readings-heading">Confirmed reading timeline</h2>
                <p className="mb-0 mt-1 text-xs text-slate-500">Only patient-confirmed records appear here.</p>
                <ol className="mb-0 mt-5 list-none divide-y divide-slate-200 p-0">
                  {data.readings.map((reading) => (
                    <li className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[150px_1fr]" key={reading.reading_id}>
                      <div>
                        <p className="m-0 text-2xl font-semibold tracking-[-0.03em]">{reading.systolic}<span className="mx-1 text-slate-300">/</span>{reading.diastolic}</p>
                        <p className="mb-0 mt-1 text-xs text-slate-500">{formatTimestamp(reading.measured_at)}</p>
                      </div>
                      <div className="text-sm">
                        <p className={`m-0 font-medium ${reading.medication_taken === "no" ? "text-amber-800" : "text-slate-700"}`}>{medicationLabels[reading.medication_taken]}</p>
                        {reading.missed_medication_reason_code ? <p className="mb-0 mt-1 text-xs text-slate-500">Recorded reason: {reading.missed_medication_reason_code.replaceAll("_", " ")}</p> : null}
                        {reading.context_codes.length ? <p className="mb-0 mt-1 text-xs text-slate-500">Context: {reading.context_codes.map((code) => code.replaceAll("_", " ")).join(", ")}</p> : null}
                        {reading.note ? <p className="mb-0 mt-2 rounded-lg bg-slate-50 p-2 text-xs text-slate-600">{reading.note}</p> : null}
                      </div>
                    </li>
                  ))}
                </ol>
              </section>

              <section aria-labelledby="contact-heading" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_34px_rgba(15,23,42,0.04)] sm:p-6">
                <h2 className="m-0 text-lg font-semibold" id="contact-heading">Contact attempts</h2>
                <p className="mb-0 mt-1 text-xs text-slate-500">Internal records for this synthetic follow-up task.</p>
                {data.allowed_actions.can_record_contact ? (
                  <form className="mt-5 grid gap-3 sm:grid-cols-2" onSubmit={submitContact}>
                    <label className="grid gap-1.5 text-xs font-medium text-slate-600">Contact outcome
                      <select className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm" onChange={(event) => setContactOutcome(event.target.value)} value={contactOutcome}>
                        <option value="reached">Reached patient</option><option value="no_answer">No answer</option><option value="message_left">Message left</option><option value="follow_up_scheduled">Follow-up scheduled</option>
                      </select>
                    </label>
                    <label className="grid gap-1.5 text-xs font-medium text-slate-600 sm:col-span-2">Contact note <span className="font-normal text-slate-400">Optional</span>
                      <textarea className="min-h-20 rounded-lg border border-slate-300 p-3 text-sm" maxLength={1000} onChange={(event) => setContactNote(event.target.value)} value={contactNote} />
                    </label>
                    <button className="rounded-lg bg-[#075e54] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2" disabled={pendingAction !== null} type="submit">{pendingAction === "contact-attempts" ? "Recording…" : "Record contact attempt"}</button>
                  </form>
                ) : null}
                {data.contact_attempts.length ? <ol className="mb-0 mt-5 list-none divide-y divide-slate-200 p-0">{data.contact_attempts.map((attempt) => <li className="py-3 text-sm" key={attempt.contact_attempt_id}><div className="flex flex-wrap justify-between gap-2"><p className="m-0 font-semibold capitalize">{attempt.outcome_code.replaceAll("_", " ")}</p><p className="m-0 text-xs text-slate-500">{formatTimestamp(attempt.attempted_at)}</p></div><p className="mb-0 mt-1 text-xs text-slate-500">{attempt.clinician.display_name} · {channelLabels[attempt.channel]}</p>{attempt.note ? <p className="mb-0 mt-2 text-sm text-slate-700">{attempt.note}</p> : null}</li>)}</ol> : <p className="mb-0 mt-5 text-sm text-slate-500">No contact attempts recorded.</p>}
              </section>

              <section aria-labelledby="messages-heading" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_34px_rgba(15,23,42,0.04)] sm:p-6">
                <div className="mb-5 rounded-xl border border-violet-200 bg-violet-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="m-0 text-sm font-semibold">AI-generated case brief</h2><p className="mb-0 mt-1 text-xs text-slate-600">Grounded in the confirmed readings and deterministic evidence shown on this page.</p></div><button className="rounded-lg border border-violet-300 bg-white px-3 py-2 text-xs font-semibold disabled:opacity-50" disabled={pendingAction !== null} onClick={() => void generateBrief()} type="button">{pendingAction === "case-brief" ? "Generating…" : "Generate brief"}</button></div>
                  {caseBrief ? <div className="mt-4 text-sm leading-6"><p className="font-medium">{caseBrief.summary}</p><p>{caseBrief.rule_explanation}</p>{caseBrief.timeline_points.length ? <ul>{caseBrief.timeline_points.map((point) => <li key={point}>{point}</li>)}</ul> : null}<p className="text-xs font-medium text-violet-900">{caseBrief.safety_note}</p></div> : null}
                </div>
                <h2 className="m-0 text-lg font-semibold" id="messages-heading">Patient messages</h2>
                <p className="mb-0 mt-1 text-xs leading-5 text-slate-500">Clinician-authored drafts require a separate approval before simulated sending. This is not a live WhatsApp integration.</p>
                {data.allowed_actions.can_draft_message ? (
                  <form className="mt-5 space-y-3" onSubmit={submitMessage}>
                    <label className="grid gap-1.5 text-xs font-medium text-slate-600">Message language
                      <select className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm" onChange={(event) => setMessageLanguage(event.target.value)} value={messageLanguage}><option value="en">English</option><option value="sn">Shona</option><option value="nd">Ndebele</option></select>
                    </label>
                    <label className="grid gap-1.5 text-xs font-medium text-slate-600">Clinician-authored message <span className="font-normal text-slate-400">No diagnosis or medication-change instructions</span>
                      <textarea className="min-h-28 rounded-lg border border-slate-300 p-3 text-sm" maxLength={2000} onChange={(event) => setMessageContent(event.target.value)} required value={messageContent} />
                    </label>
                    <button className="w-full rounded-lg border border-[#075e54] px-4 py-2.5 text-sm font-semibold text-[#075e54] disabled:opacity-50" disabled={pendingAction !== null || !messageContent.trim()} type="submit">{pendingAction === "draft-message" ? "Saving draft…" : "Save message draft"}</button>
                    <label className="grid gap-1.5 border-t border-slate-200 pt-3 text-xs font-medium text-slate-600">Clinician outcome for AI draft <span className="font-normal text-slate-400">The AI may only adapt this context; clinician approval remains mandatory</span><textarea className="min-h-20 rounded-lg border border-slate-300 p-3 text-sm" maxLength={1000} onChange={(event) => setClinicianOutcome(event.target.value)} value={clinicianOutcome} /></label>
                    <button className="w-full rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={pendingAction !== null || !clinicianOutcome.trim()} onClick={generateAIDraft} type="button">{pendingAction === "ai-draft-message" ? "Generating…" : "Generate AI draft for approval"}</button>
                  </form>
                ) : null}
                <div className="mt-5 space-y-3">{data.messages.length ? data.messages.map((message) => <article className="rounded-xl border border-slate-200 p-4" key={message.message_id}><div className="flex flex-wrap items-center justify-between gap-2"><span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold capitalize">{message.approval_status}</span><span className="text-xs text-slate-500">{languageLabels[message.language]} · {message.generation_type === "clinician_authored" ? "Clinician-authored" : "AI-generated draft"}</span></div><p className="mb-0 mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{message.content}</p>{message.approval_status === "draft" && data.allowed_actions.can_draft_message ? <button className="mt-3 rounded-lg bg-[#075e54] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50" disabled={pendingAction !== null} onClick={() => void runAction("approve-message", { message_id: message.message_id, send: false })} type="button">Approve message</button> : null}{message.approval_status === "approved" && data.allowed_actions.can_draft_message ? <button className="mt-3 rounded-lg bg-[#075e54] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50" disabled={pendingAction !== null} onClick={() => void runAction("approve-message", { message_id: message.message_id, send: true })} type="button">Send in simulator</button> : null}{message.approval_status === "sent" ? <p className="mb-0 mt-3 text-xs font-medium text-emerald-700">Sent to the demonstration channel · not verified as delivered</p> : null}</article>) : <p className="m-0 text-sm text-slate-500">No patient messages drafted.</p>}</div>
              </section>

              <section aria-labelledby="audit-heading" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_34px_rgba(15,23,42,0.04)] sm:p-6">
                <h2 className="m-0 text-lg font-semibold" id="audit-heading">Audit timeline</h2>
                <ol className="mb-0 mt-5 list-none space-y-4 border-l border-slate-200 p-0 pl-5">{data.audit_events.length ? data.audit_events.map((event) => <li className="relative" key={event.audit_event_id}><span aria-hidden="true" className="absolute -left-[1.45rem] top-1 size-2 rounded-full bg-[#08766b]" /><p className="m-0 text-sm font-semibold capitalize">{event.event_type.replaceAll("review_task.", "").replaceAll("_", " ")}</p><p className="mb-0 mt-1 text-xs text-slate-500">{event.actor_display_name} · {formatTimestamp(event.created_at)}</p></li>) : <li className="text-sm text-slate-500">No task activity recorded.</li>}</ol>
              </section>
            </div>

            <aside aria-labelledby="workflow-heading" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_12px_40px_rgba(15,23,42,0.06)] lg:sticky lg:top-6">
              <h2 className="m-0 text-lg font-semibold" id="workflow-heading">Task workflow</h2>
              <p className="mb-0 mt-1 text-xs leading-5 text-slate-500">Actions are checked and recorded by the backend.</p>

              <dl className="mt-5 grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-4 text-sm">
                <div><dt className="text-xs text-slate-500">Owner</dt><dd className="m-0 mt-1 font-medium">{data.task.assigned_owner?.display_name ?? "Unassigned"}</dd></div>
                <div><dt className="text-xs text-slate-500">Acknowledged</dt><dd className="m-0 mt-1 font-medium">{data.acknowledged_at ? formatTimestamp(data.acknowledged_at) : "Not yet"}</dd></div>
              </dl>

              {actionError ? <p aria-live="assertive" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-800">{actionError}</p> : null}

              {data.allowed_actions.can_assign ? (
                <form className="mt-5 border-t border-slate-200 pt-5" onSubmit={submitAssignment}>
                  <label className="grid gap-1.5 text-xs font-medium text-slate-600">
                    Assign owner
                    <select className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm" onChange={(event) => setOwnerId(event.target.value)} value={ownerId}>
                      {data.available_owners.map((owner) => <option key={owner.clinician_id} value={owner.clinician_id}>{owner.display_name} · {owner.display_role}</option>)}
                    </select>
                  </label>
                  <button className="mt-3 w-full rounded-lg border border-[#075e54] px-4 py-2.5 text-sm font-semibold text-[#075e54] disabled:opacity-50" disabled={pendingAction !== null} type="submit">{pendingAction === "assign" ? "Saving…" : data.task.status === "open" ? "Assign task" : data.task.status === "in_review" ? "Return and assign" : "Update owner"}</button>
                  {data.allowed_actions.can_unassign ? <button className="mt-2 w-full px-4 py-2 text-sm font-semibold text-slate-600 underline-offset-4 hover:underline disabled:opacity-50" disabled={pendingAction !== null} onClick={() => void runAction("assign", { clinician_id: null })} type="button">Unassign task</button> : null}
                </form>
              ) : null}

              <div className="mt-5 space-y-2 border-t border-slate-200 pt-5">
                {data.allowed_actions.can_acknowledge ? <button className="w-full rounded-lg bg-[#075e54] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={pendingAction !== null} onClick={() => void runAction("acknowledge")} type="button">{pendingAction === "acknowledge" ? "Acknowledging…" : "Acknowledge task"}</button> : null}
                {data.allowed_actions.can_start_review ? <button className="w-full rounded-lg bg-[#075e54] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={pendingAction !== null} onClick={() => void runAction("start-review")} type="button">{pendingAction === "start-review" ? "Starting…" : "Start review"}</button> : null}
                {data.task.status === "assigned" && !data.allowed_actions.can_acknowledge && !data.allowed_actions.can_start_review ? <p className="m-0 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900">This task is assigned to another fictional clinician. Reassign it before acting.</p> : null}
              </div>

              {data.allowed_actions.can_resolve ? (
                <form className="mt-5 space-y-3 border-t border-slate-200 pt-5" onSubmit={submitResolution}>
                  <h3 className="m-0 text-sm font-semibold">Record outcome</h3>
                  <label className="grid gap-1.5 text-xs font-medium text-slate-600">Outcome
                    <select className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm" onChange={(event) => setOutcomeCode(event.target.value)} value={outcomeCode}>
                      <option value="review_completed">Review completed</option>
                      <option value="follow_up_planned">Follow-up planned</option>
                      <option value="unable_to_reach">Unable to reach</option>
                      <option value="duplicate_or_invalid_record">Duplicate or invalid record</option>
                    </select>
                  </label>
                  <label className="grid gap-1.5 text-xs font-medium text-slate-600">Outcome note <span className="font-normal text-slate-400">Optional; no medication instructions</span>
                    <textarea className="min-h-24 rounded-lg border border-slate-300 p-3 text-sm" maxLength={1000} onChange={(event) => setOutcomeNote(event.target.value)} value={outcomeNote} />
                  </label>
                  <button className="w-full rounded-lg bg-[#075e54] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={pendingAction !== null} type="submit">{pendingAction === "resolve" ? "Resolving…" : "Resolve task"}</button>
                </form>
              ) : null}

              {data.task.status === "resolved" ? (
                <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm">
                  <p className="m-0 font-semibold text-emerald-900">Resolution recorded</p>
                  <p className="mb-0 mt-1 text-xs text-emerald-800">{data.outcome_code?.replaceAll("_", " ")}{data.outcome_note ? ` · ${data.outcome_note}` : ""}</p>
                </div>
              ) : null}

              {data.allowed_actions.can_reopen ? (
                <form className="mt-5 space-y-3 border-t border-slate-200 pt-5" onSubmit={submitReopen}>
                  <label className="grid gap-1.5 text-xs font-medium text-slate-600">Reason to reopen
                    <textarea className="min-h-20 rounded-lg border border-slate-300 p-3 text-sm" maxLength={500} onChange={(event) => setReopenReason(event.target.value)} required value={reopenReason} />
                  </label>
                  <button className="w-full rounded-lg border border-[#075e54] px-4 py-2.5 text-sm font-semibold text-[#075e54] disabled:opacity-50" disabled={pendingAction !== null || !reopenReason.trim()} type="submit">{pendingAction === "reopen" ? "Reopening…" : "Reopen review"}</button>
                </form>
              ) : null}

              <p className="mb-0 mt-5 border-t border-slate-200 pt-5 text-xs leading-5 text-slate-500">No diagnosis, prescribing, dose-change, or medication-edit control exists. Workflow priority remains deterministic.</p>
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
