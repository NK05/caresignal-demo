import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ClinicianTaskDetailData, TaskStatus } from "@/lib/clinician";

import ClinicianTaskDetailPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ taskId: "51000000-0000-4000-8000-000000000001" }),
}));

const doctor = {
  clinician_id: "21000000-0000-4000-8000-000000000001",
  display_name: "Dr Chipo Moyo",
  display_role: "Doctor",
};

const nurse = {
  clinician_id: "21000000-0000-4000-8000-000000000002",
  display_name: "Nurse Thandi Ncube",
  display_role: "Chronic-care nurse",
};

function detail(status: TaskStatus): ClinicianTaskDetailData {
  const assigned = status !== "open";
  const acknowledged = status === "in_review" || status === "resolved";
  return {
    generated_at: "2026-07-17T12:00:00Z",
    synthetic_data: true,
    task: {
      task_id: "51000000-0000-4000-8000-000000000001",
      patient_id: "11000000-0000-4000-8000-000000000004",
      patient_synthetic_identifier: "CS-PAT-004",
      patient_display_name: "Nomsa Dube",
      preferred_language: "nd",
      preferred_channel: "whatsapp_simulator",
      priority: "urgent_review",
      status,
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
      assigned_owner: assigned ? doctor : null,
      evidence_count: 1,
      opened_at: "2026-07-17T10:00:00Z",
      due_at: "2026-07-17T11:30:00Z",
      task_age_minutes: 120,
      overdue: status !== "resolved",
      unacknowledged: status === "assigned" && !acknowledged,
    },
    acknowledged_at: acknowledged ? "2026-07-17T12:02:00Z" : null,
    resolved_at: status === "resolved" ? "2026-07-17T12:10:00Z" : null,
    outcome_code: status === "resolved" ? "follow_up_planned" : null,
    outcome_note: status === "resolved" ? "Synthetic follow-up arranged." : null,
    reopened_count: 0,
    readings: [
      {
        reading_id: "41000000-0000-4000-8000-000000000006",
        systolic: 186,
        diastolic: 122,
        measured_at: "2026-07-17T10:00:00Z",
        confirmed_at: "2026-07-17T10:01:00Z",
        medication_taken: "yes",
        missed_medication_reason_code: null,
        context_codes: [],
        note: null,
      },
    ],
    evidence: [
      {
        rule_evaluation_id: "50000000-0000-4000-8000-000000000001",
        reading_id: "41000000-0000-4000-8000-000000000006",
        rule_id: "demo-single-reading-review",
        rule_version: "demo-2026.07.1",
        priority: "urgent_review",
        title: "Single-reading review marker",
        reason: "A synthetic confirmed reading met the configured demo marker.",
        source_reference: "Illustrative prototype configuration—not clinically validated",
        evaluated_at: "2026-07-17T10:00:00Z",
        observed_values: [],
      },
    ],
    available_owners: [doctor, nurse],
    current_clinician: doctor,
    allowed_actions: {
      can_assign: status !== "resolved",
      can_unassign: status === "assigned",
      can_acknowledge: status === "assigned" && !acknowledged,
      can_start_review: status === "assigned" && acknowledged,
      can_return_to_assigned: status === "in_review",
      can_resolve: status === "in_review",
      can_reopen: status === "resolved",
      can_record_contact: status === "in_review",
      can_draft_message: status === "in_review",
    },
    contact_attempts: [],
    messages: [],
    audit_events: [],
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ClinicianTaskDetailPage", () => {
  it("shows confirmed readings, deterministic evidence, and safety boundaries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => detail("open") }),
    );

    render(<ClinicianTaskDetailPage />);

    expect(await screen.findByRole("heading", { name: "CS-PAT-004" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rule evidence" })).toBeInTheDocument();
    expect(screen.getByText(/illustrative prototype configuration/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Confirmed reading timeline" })).toBeInTheDocument();
    expect(screen.getByText("Reported taken")).toBeInTheDocument();
    expect(screen.getByText("Ndebele")).toBeInTheDocument();
    expect(screen.getByText("WhatsApp simulator")).toBeInTheDocument();
    expect(screen.getByText(/no diagnosis, prescribing, dose-change/i)).toBeInTheDocument();
  });

  it("completes assignment, acknowledgement, review, and resolution controls", async () => {
    const assigned = detail("assigned");
    const reviewing = detail("in_review");
    const resolved = detail("resolved");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => detail("open") })
      .mockResolvedValueOnce({ ok: true, json: async () => assigned })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...assigned,
          acknowledged_at: "2026-07-17T12:02:00Z",
          task: { ...assigned.task, unacknowledged: false },
          allowed_actions: {
            ...assigned.allowed_actions,
            can_acknowledge: false,
            can_start_review: true,
          },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => reviewing })
      .mockResolvedValueOnce({ ok: true, json: async () => resolved });
    vi.stubGlobal("fetch", fetchMock);

    render(<ClinicianTaskDetailPage />);
    await screen.findByRole("button", { name: "Assign task" });

    fireEvent.click(screen.getByRole("button", { name: "Assign task" }));
    expect(await screen.findByRole("button", { name: "Acknowledge task" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge task" }));
    expect(await screen.findByRole("button", { name: "Start review" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start review" }));
    expect(await screen.findByRole("button", { name: "Resolve task" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/outcome note/i), {
      target: { value: "Synthetic follow-up arranged." },
    });
    fireEvent.change(screen.getByLabelText("Outcome"), {
      target: { value: "follow_up_planned" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Resolve task" }));

    expect(await screen.findByText("Resolution recorded")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/assign$/);
    expect(fetchMock.mock.calls[4][0]).toMatch(/\/resolve$/);
    expect(fetchMock.mock.calls[4][1]?.body).toContain("follow_up_planned");
  });

  it("surfaces a backend action error without replacing the task evidence", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => detail("open") })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Task action requires the assigned clinician" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<ClinicianTaskDetailPage />);
    await screen.findByRole("button", { name: "Assign task" });

    fireEvent.click(screen.getByRole("button", { name: "Assign task" }));

    expect(
      await screen.findByText("Task action requires the assigned clinician"),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/illustrative prototype configuration/i)).toBeInTheDocument());
  });

  it("records contact and requires approval before simulated message sending", async () => {
    const reviewing = detail("in_review");
    const withContact: ClinicianTaskDetailData = {
      ...reviewing,
      contact_attempts: [{
        contact_attempt_id: "61000000-0000-4000-8000-000000000001",
        clinician: doctor,
        channel: "whatsapp_simulator",
        outcome_code: "message_left",
        note: "Synthetic contact note.",
        attempted_at: "2026-07-17T12:03:00Z",
      }],
    };
    const draftMessage = {
      message_id: "62000000-0000-4000-8000-000000000001",
      channel: "whatsapp_simulator" as const,
      language: "nd" as const,
      content: "Sicela ubuye eklinikhi.",
      generation_type: "clinician_authored" as const,
      approval_status: "draft" as const,
      approved_by: null,
      approved_at: null,
      sent_at: null,
      delivery_status: "not_sent" as const,
      created_at: "2026-07-17T12:04:00Z",
    };
    const withDraft = { ...withContact, messages: [draftMessage] };
    const withApproval = {
      ...withDraft,
      messages: [{
        ...draftMessage,
        approval_status: "approved" as const,
        approved_by: doctor.clinician_id,
        approved_at: "2026-07-17T12:05:00Z",
      }],
    };
    const withSent = {
      ...withApproval,
      messages: [{
        ...withApproval.messages[0],
        approval_status: "sent" as const,
        delivery_status: "sent" as const,
        sent_at: "2026-07-17T12:06:00Z",
      }],
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => reviewing })
      .mockResolvedValueOnce({ ok: true, json: async () => withContact })
      .mockResolvedValueOnce({ ok: true, json: async () => withDraft })
      .mockResolvedValueOnce({ ok: true, json: async () => withApproval })
      .mockResolvedValueOnce({ ok: true, json: async () => withSent });
    vi.stubGlobal("fetch", fetchMock);
    render(<ClinicianTaskDetailPage />);
    await screen.findByRole("button", { name: "Record contact attempt" });

    fireEvent.change(screen.getByLabelText("Contact outcome"), { target: { value: "message_left" } });
    fireEvent.change(screen.getByLabelText(/contact note/i), { target: { value: "Synthetic contact note." } });
    fireEvent.click(screen.getByRole("button", { name: "Record contact attempt" }));
    expect(await screen.findByText("Message left")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/clinician-authored message/i), { target: { value: draftMessage.content } });
    fireEvent.click(screen.getByRole("button", { name: "Save message draft" }));
    fireEvent.click(await screen.findByRole("button", { name: "Approve message" }));
    fireEvent.click(await screen.findByRole("button", { name: "Send in simulator" }));

    expect(await screen.findByText(/sent to the demonstration channel/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls[3][1]?.body).toContain('"send":false');
    expect(fetchMock.mock.calls[4][1]?.body).toContain('"send":true');
  });
});
