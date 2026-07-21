"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type {
  ClinicianDashboardData,
  ClinicianTask,
  Language,
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

const languageLabels: Record<Language, string> = {
  en: "English",
  sn: "Shona",
  nd: "Ndebele",
  mixed: "Mixed",
  unknown: "Unknown",
};

interface Filters {
  priority: "all" | TaskPriority;
  status: "all" | TaskStatus;
  owner: "all" | "unassigned" | string;
  language: "all" | Language;
  overdue: "all" | "true" | "false";
  medication: "all" | "true" | "false";
}

const defaultFilters: Filters = {
  priority: "all",
  status: "all",
  owner: "all",
  language: "all",
  overdue: "all",
  medication: "all",
};

function formatAge(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-ZW", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function matchesFilters(task: ClinicianTask, filters: Filters) {
  if (filters.priority !== "all" && task.priority !== filters.priority) return false;
  if (filters.status !== "all" && task.status !== filters.status) return false;
  if (filters.owner === "unassigned" && task.assigned_owner !== null) return false;
  if (
    filters.owner !== "all" &&
    filters.owner !== "unassigned" &&
    task.assigned_owner?.clinician_id !== filters.owner
  ) {
    return false;
  }
  if (filters.language !== "all" && task.preferred_language !== filters.language) return false;
  if (filters.overdue !== "all" && task.overdue !== (filters.overdue === "true")) return false;
  if (
    filters.medication !== "all" &&
    task.medication_adherence_signal !== (filters.medication === "true")
  ) {
    return false;
  }
  return true;
}

function MetricIcon({ type }: { type: "person" | "clock" | "review" | "alert" | "check" }) {
  const paths = {
    person: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0" />,
    clock: <path d="M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />,
    review: <path d="M9 5h10M9 12h10M9 19h6M5 5h.01M5 12h.01M5 19h.01" />,
    alert: <path d="M12 9v4m0 4h.01M10.3 4.7 3.5 17a2 2 0 0 0 1.75 3h13.5a2 2 0 0 0 1.75-3L13.7 4.7a2 2 0 0 0-3.4 0Z" />,
    check: <path d="m5 12 4 4L19 6" />,
  };
  return (
    <svg aria-hidden="true" className="size-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" viewBox="0 0 24 24">
      {paths[type]}
    </svg>
  );
}

function LoadingDashboard() {
  return (
    <div aria-live="polite" className="space-y-5" role="status">
      <span className="sr-only">Loading clinician dashboard</span>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, index) => (
          <div className="h-28 animate-pulse rounded-2xl border border-slate-200 bg-white" key={index} />
        ))}
      </div>
      <div className="h-80 animate-pulse rounded-2xl border border-slate-200 bg-white" />
    </div>
  );
}

export default function ClinicianDashboardPage() {
  const [data, setData] = useState<ClinicianDashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requestKey, setRequestKey] = useState(0);
  const [filters, setFilters] = useState<Filters>(defaultFilters);

  useEffect(() => {
    let active = true;
    async function loadDashboard() {
      setError(null);
      try {
        const response = await fetch("/api/clinician/dashboard", { cache: "no-store" });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Unable to load the clinician workspace.");
        if (active) setData(body as ClinicianDashboardData);
      } catch (reason) {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Unable to load the clinician workspace.");
        }
      }
    }
    void loadDashboard();
    return () => {
      active = false;
    };
  }, [requestKey]);

  const visibleTasks = useMemo(
    () => data?.tasks.filter((task) => matchesFilters(task, filters)) ?? [],
    [data, filters],
  );
  const activeFilterCount = Object.values(filters).filter((value) => value !== "all").length;

  const metrics = data
    ? [
        { label: "Unassigned", value: data.summary.unassigned, icon: "person" as const },
        {
          label: "Awaiting acknowledgement",
          value: data.summary.awaiting_acknowledgement,
          icon: "clock" as const,
        },
        { label: "In review", value: data.summary.in_review, icon: "review" as const },
        { label: "Overdue", value: data.summary.overdue, icon: "alert" as const },
        { label: "Resolved today", value: data.summary.resolved_today, icon: "check" as const },
      ]
    : [];

  return (
    <div className="min-h-screen bg-[#f4f7f9] text-slate-950">
      <header className="border-b border-emerald-950/10 bg-[#063f3a] text-white lg:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <Link className="flex items-center gap-2 font-semibold" href="/">
            <span className="grid size-8 place-items-center rounded-lg bg-white text-sm font-bold text-[#075e54]">C</span>
            CareSignal
          </Link>
          <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[11px]">Synthetic clinic</span>
        </div>
      </header>

      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col bg-[#063f3a] px-5 py-6 text-white lg:flex">
        <Link className="flex items-center gap-3" href="/">
          <span className="grid size-10 place-items-center rounded-xl bg-white text-lg font-bold text-[#075e54]">C</span>
          <div>
            <p className="m-0 font-semibold">CareSignal</p>
            <p className="m-0 text-xs text-emerald-100/70">Clinical follow-up</p>
          </div>
        </Link>
        <nav aria-label="Clinician workspace" className="mt-10 space-y-2">
          <span aria-current="page" className="flex items-center gap-3 rounded-xl bg-white/12 px-3 py-3 text-sm font-medium">
            <MetricIcon type="review" /> Review queue
          </span>
          <span className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-emerald-100/60">
            <MetricIcon type="person" /> Patients
          </span>
          <span className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-emerald-100/60">
            <MetricIcon type="check" /> Resolved
          </span>
        </nav>
        <div className="mt-auto rounded-2xl border border-white/10 bg-black/10 p-4">
          <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-100/60">Demo clinician</p>
          <p className="mb-0 mt-2 text-sm font-semibold">Dr Chipo Moyo</p>
          <p className="m-0 text-xs text-emerald-100/70">Fictional identity</p>
        </div>
      </aside>

      <main className="px-4 py-6 sm:px-6 lg:ml-64 lg:px-9 lg:py-8">
        <div className="mx-auto max-w-[1500px]">
          <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#08766b]">Clinician workspace</p>
              <h1 className="m-0 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Review queue</h1>
              <p className="mb-0 mt-2 text-sm text-slate-600">Prioritised by deterministic workflow rules, then age.</p>
            </div>
            <div className="flex items-center gap-2 self-start rounded-full border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-900 sm:self-auto">
              <span aria-hidden="true" className="size-2 rounded-full bg-emerald-600" />
              Synthetic data only
            </div>
          </div>

          {error ? (
            <section aria-live="assertive" className="rounded-2xl border border-rose-200 bg-white p-6 shadow-sm">
              <p className="m-0 font-semibold text-rose-900">Dashboard unavailable</p>
              <p className="mb-0 mt-2 text-sm text-slate-600">{error}</p>
              <button className="mt-4 rounded-lg bg-[#075e54] px-4 py-2 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#075e54]" onClick={() => setRequestKey((key) => key + 1)} type="button">
                Try again
              </button>
            </section>
          ) : !data ? (
            <LoadingDashboard />
          ) : (
            <>
              <section aria-label="Queue summary" className="grid grid-cols-2 gap-3 lg:grid-cols-5">
                {metrics.map((metric) => (
                  <article className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-[0_8px_28px_rgba(15,23,42,0.04)] sm:p-5" key={metric.label}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="m-0 text-2xl font-semibold tracking-[-0.03em] sm:text-3xl">{metric.value}</p>
                        <p className="mb-0 mt-1 text-xs leading-5 text-slate-600 sm:text-sm">{metric.label}</p>
                      </div>
                      <span className={`grid size-9 place-items-center rounded-xl ${metric.label === "Overdue" && metric.value > 0 ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-[#08766b]"}`}>
                        <MetricIcon type={metric.icon} />
                      </span>
                    </div>
                  </article>
                ))}
              </section>

              <section aria-labelledby="queue-heading" className="mt-5 overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-[0_12px_40px_rgba(15,23,42,0.05)]">
                <div className="border-b border-slate-200 px-4 py-5 sm:px-5">
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                    <div>
                      <h2 className="m-0 text-lg font-semibold" id="queue-heading">Active follow-up</h2>
                      <p aria-live="polite" className="mb-0 mt-1 text-xs text-slate-500">
                        Showing {visibleTasks.length} of {data.tasks.length} tasks · Updated {formatTimestamp(data.generated_at)}
                      </p>
                    </div>
                    {activeFilterCount > 0 ? (
                      <button className="self-start text-sm font-semibold text-[#08766b] underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#075e54]" onClick={() => setFilters(defaultFilters)} type="button">
                        Clear {activeFilterCount} filter{activeFilterCount === 1 ? "" : "s"}
                      </button>
                    ) : null}
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                    <FilterSelect label="Priority" value={filters.priority} onChange={(value) => setFilters((current) => ({ ...current, priority: value as Filters["priority"] }))}>
                      <option value="all">All priorities</option>
                      <option value="urgent_review">Urgent review</option>
                      <option value="needs_review">Needs review</option>
                      <option value="watch">Watch</option>
                      <option value="routine">Routine</option>
                    </FilterSelect>
                    <FilterSelect label="Status" value={filters.status} onChange={(value) => setFilters((current) => ({ ...current, status: value as Filters["status"] }))}>
                      <option value="all">All active</option>
                      <option value="open">Open</option>
                      <option value="assigned">Assigned</option>
                      <option value="in_review">In review</option>
                    </FilterSelect>
                    <FilterSelect label="Owner" value={filters.owner} onChange={(value) => setFilters((current) => ({ ...current, owner: value }))}>
                      <option value="all">All owners</option>
                      <option value="unassigned">Unassigned</option>
                      {data.available_owners.map((owner) => (
                        <option key={owner.clinician_id} value={owner.clinician_id}>{owner.display_name}</option>
                      ))}
                    </FilterSelect>
                    <FilterSelect label="Language" value={filters.language} onChange={(value) => setFilters((current) => ({ ...current, language: value as Filters["language"] }))}>
                      <option value="all">All languages</option>
                      <option value="en">English</option>
                      <option value="sn">Shona</option>
                      <option value="nd">Ndebele</option>
                    </FilterSelect>
                    <FilterSelect label="Due state" value={filters.overdue} onChange={(value) => setFilters((current) => ({ ...current, overdue: value as Filters["overdue"] }))}>
                      <option value="all">All due states</option>
                      <option value="true">Overdue</option>
                      <option value="false">Not overdue</option>
                    </FilterSelect>
                    <FilterSelect label="Medication context" value={filters.medication} onChange={(value) => setFilters((current) => ({ ...current, medication: value as Filters["medication"] }))}>
                      <option value="all">All contexts</option>
                      <option value="true">Follow-up recorded</option>
                      <option value="false">No follow-up marker</option>
                    </FilterSelect>
                  </div>
                </div>

                <div className="hidden grid-cols-[1.25fr_1fr_0.8fr_0.8fr_1fr_0.65fr] gap-4 border-b border-slate-200 bg-slate-50/80 px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500 lg:grid">
                  <span>Patient & marker</span><span>Latest reading</span><span>Priority</span><span>Status</span><span>Owner</span><span className="text-right">Age</span>
                </div>
                {visibleTasks.length === 0 ? (
                  <div className="px-5 py-14 text-center">
                    <p className="m-0 font-semibold">No tasks match these filters.</p>
                    <p className="mb-0 mt-2 text-sm text-slate-500">Clear one or more filters to restore the queue.</p>
                  </div>
                ) : (
                  <ul className="m-0 list-none divide-y divide-slate-200 p-0">
                    {visibleTasks.map((task) => (
                      <TaskRow key={task.task_id} task={task} />
                    ))}
                  </ul>
                )}
              </section>

              <p className="mx-auto mb-0 mt-5 max-w-3xl text-center text-xs leading-5 text-slate-500">
                Internal priorities are generated only by versioned demo rules. They are not diagnoses, medication advice, or emergency decisions. Configuration is illustrative and not clinically validated.
              </p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function FilterSelect({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  return (
    <label className="grid gap-1.5 text-xs font-medium text-slate-600">
      {label}
      <select className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800 focus:border-[#08766b] focus:outline-none focus:ring-2 focus:ring-emerald-100" onChange={(event) => onChange(event.target.value)} value={value}>
        {children}
      </select>
    </label>
  );
}

function TaskRow({ task }: { task: ClinicianTask }) {
  return (
    <li>
      <Link
        aria-label={`Open task for ${task.patient_synthetic_identifier}`}
        className={`grid gap-4 px-4 py-5 no-underline transition-colors hover:bg-slate-50/70 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[#075e54] sm:px-5 lg:grid-cols-[1.25fr_1fr_0.8fr_0.8fr_1fr_0.65fr] lg:items-center ${task.overdue ? "border-l-4 border-l-rose-500" : "border-l-4 border-l-transparent"}`}
        href={`/clinician/tasks/${task.task_id}`}
      >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="m-0 font-semibold text-slate-950">{task.patient_synthetic_identifier}</p>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">{languageLabels[task.preferred_language]}</span>
          {task.overdue ? <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-800">Overdue</span> : null}
        </div>
        <p className="mb-0 mt-1 truncate text-sm font-medium text-slate-700">{task.flag_title}</p>
        <p className="mb-0 mt-1 line-clamp-1 text-xs text-slate-500">{task.patient_display_name} · {task.evidence_count} evidence record{task.evidence_count === 1 ? "" : "s"}</p>
      </div>
      <div>
        <p className="m-0 text-lg font-semibold tracking-[-0.02em]">{task.latest_reading.systolic}<span className="mx-1 text-slate-300">/</span>{task.latest_reading.diastolic}</p>
        <p className="mb-0 mt-1 text-xs text-slate-500">{formatTimestamp(task.latest_reading.measured_at)}</p>
        {task.medication_adherence_signal ? <p className="mb-0 mt-1 text-xs font-medium text-amber-800">Medication follow-up recorded</p> : null}
      </div>
      <div className="flex items-center justify-between gap-3 lg:block">
        <span className="text-xs font-medium text-slate-500 lg:hidden">Priority</span>
        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${priorityStyles[task.priority]}`}>{priorityLabels[task.priority]}</span>
      </div>
      <div className="flex items-center justify-between gap-3 text-sm lg:block">
        <span className="text-xs font-medium text-slate-500 lg:hidden">Status</span>
        <p className="m-0 font-medium">{statusLabels[task.status]}</p>
        {task.unacknowledged ? <p className="mb-0 mt-1 text-xs text-amber-800">Awaiting acknowledgement</p> : null}
      </div>
      <div className="flex items-center justify-between gap-3 text-sm lg:block">
        <span className="text-xs font-medium text-slate-500 lg:hidden">Owner</span>
        <p className="m-0 font-medium">{task.assigned_owner?.display_name ?? "Unassigned"}</p>
        <p className="mb-0 mt-1 text-xs text-slate-500">{task.assigned_owner?.display_role ?? "Needs owner"}</p>
      </div>
      <div className="flex items-center justify-between gap-3 lg:block lg:text-right">
        <span className="text-xs font-medium text-slate-500 lg:hidden">Task age</span>
        <p className="m-0 text-sm font-semibold">{formatAge(task.task_age_minutes)}</p>
        <p className={`mb-0 mt-1 text-xs ${task.overdue ? "font-semibold text-rose-700" : "text-slate-500"}`}>{task.overdue ? "Past due" : task.due_at ? `Due ${formatTimestamp(task.due_at)}` : "No due time"}</p>
      </div>
      </Link>
    </li>
  );
}
