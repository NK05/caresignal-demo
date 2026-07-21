import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ClinicianDashboardData, ClinicianTask } from "@/lib/clinician";

import ClinicianDashboardPage from "./page";

const owner = {
  clinician_id: "21000000-0000-4000-8000-000000000001",
  display_name: "Dr Chipo Moyo",
  display_role: "Doctor",
};

function task(overrides: Partial<ClinicianTask>): ClinicianTask {
  return {
    task_id: "51000000-0000-4000-8000-000000000001",
    patient_id: "11000000-0000-4000-8000-000000000004",
    patient_synthetic_identifier: "CS-PAT-004",
    patient_display_name: "Nomsa Dube",
    preferred_language: "nd",
    preferred_channel: "whatsapp_simulator",
    priority: "urgent_review",
    status: "open",
    flag_title: "Single-reading review marker",
    flag_reason: "A synthetic confirmed reading met the configured demo marker.",
    rule_version: "demo-2026.07.1",
    latest_reading: {
      reading_id: "41000000-0000-4000-8000-000000000006",
      systolic: 186,
      diastolic: 122,
      measured_at: "2026-07-17T10:00:00Z",
      medication_taken: "yes",
    },
    medication_adherence_signal: false,
    assigned_owner: null,
    evidence_count: 1,
    opened_at: "2026-07-17T10:00:00Z",
    due_at: "2026-07-17T11:30:00Z",
    task_age_minutes: 120,
    overdue: true,
    unacknowledged: false,
    ...overrides,
  };
}

const dashboard: ClinicianDashboardData = {
  generated_at: "2026-07-17T12:00:00Z",
  synthetic_data: true,
  summary: {
    unassigned: 1,
    awaiting_acknowledgement: 0,
    in_review: 1,
    overdue: 1,
    resolved_today: 0,
  },
  available_owners: [owner],
  tasks: [
    task({}),
    task({
      task_id: "51000000-0000-4000-8000-000000000002",
      patient_id: "11000000-0000-4000-8000-000000000003",
      patient_synthetic_identifier: "CS-PAT-003",
      patient_display_name: "Tawanda Chikore",
      preferred_language: "sn",
      priority: "watch",
      status: "in_review",
      flag_title: "Medication follow-up marker",
      latest_reading: {
        reading_id: "41000000-0000-4000-8000-000000000005",
        systolic: 152,
        diastolic: 96,
        measured_at: "2026-07-17T09:00:00Z",
        medication_taken: "no",
      },
      medication_adherence_signal: true,
      assigned_owner: owner,
      evidence_count: 2,
      opened_at: "2026-07-17T09:00:00Z",
      due_at: "2026-07-18T09:00:00Z",
      task_age_minutes: 180,
      overdue: false,
    }),
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ClinicianDashboardPage", () => {
  it("shows the synthetic safety boundary, summary, and prioritised tasks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => dashboard,
      }),
    );

    render(<ClinicianDashboardPage />);

    expect(await screen.findByRole("heading", { name: "Review queue" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic data only")).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Queue summary" });
    expect(within(summary).getByText("Unassigned")).toBeInTheDocument();
    expect(within(summary).getByText("Resolved today")).toBeInTheDocument();
    expect(screen.getByText("CS-PAT-004")).toBeInTheDocument();
    expect(screen.getAllByText("Urgent review").length).toBeGreaterThan(0);
    expect(screen.getByText("Medication follow-up recorded")).toBeInTheDocument();
    expect(screen.getByText(/not diagnoses, medication advice, or emergency decisions/i)).toBeInTheDocument();
  });

  it("filters the queue by priority and clears the active filter", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => dashboard,
      }),
    );
    render(<ClinicianDashboardPage />);
    await screen.findByText("CS-PAT-004");

    fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "watch" } });

    expect(screen.queryByText("CS-PAT-004")).not.toBeInTheDocument();
    expect(screen.getByText("CS-PAT-003")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear 1 filter" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear 1 filter" }));
    expect(screen.getByText("CS-PAT-004")).toBeInTheDocument();
  });

  it("shows a retryable error without inventing fallback clinical data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("API unavailable")));
    render(<ClinicianDashboardPage />);

    expect(await screen.findByText("Dashboard unavailable")).toBeInTheDocument();
    expect(screen.getByText("API unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("CS-PAT-004")).not.toBeInTheDocument());
  });
});
