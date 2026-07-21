import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PatientPage from "./page";

const home = {
  profile: { display_name: "Tariro Moyo", synthetic_identifier: "CS-PAT-001", preferred_language: "en" },
  readings: [{ id: "reading-1", systolic: 128, diastolic: 82, measured_at: "2026-07-17T10:00:00Z" }],
  follow_up: { status: "no_follow_up", message: "No care-team follow-up is currently open.", latest_care_message: null },
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("PatientPage", () => {
  it("requires confirmation before showing a structured reading as saved", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => home })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "submission-1", candidate_payload: { systolic: 132, diastolic: 84, measured_at: "2026-07-18T10:00:00Z", medication_taken: "yes", context_codes: ["rested"] } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ acknowledgement: "Reading confirmed." }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...home, readings: [{ id: "reading-2", systolic: 132, diastolic: 84, measured_at: "2026-07-18T10:00:00Z" }, ...home.readings] }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<PatientPage />);
    expect(await screen.findByText("Tariro Moyo", { exact: false })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record blood pressure" }));
    fireEvent.change(screen.getByLabelText("Systolic"), { target: { value: "132" } });
    fireEvent.change(screen.getByLabelText("Diastolic"), { target: { value: "84" } });
    fireEvent.change(screen.getByLabelText("Measurement time"), { target: { value: "2026-07-18T10:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Review reading" }));
    expect(await screen.findByRole("heading", { name: "Confirm this reading" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm and save" }));
    expect(await screen.findByText("Reading confirmed.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});
