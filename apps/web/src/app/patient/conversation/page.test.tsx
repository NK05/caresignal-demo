import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ConversationPage from "./page";

const pending = {
  id: "submission-conversation-1",
  candidate_payload: {
    systolic: 168,
    diastolic: 105,
    measured_at: "2026-07-18T09:30:00Z",
    medication_taken: "yes",
    context_codes: ["rested"],
  },
};

const emptyConversation = {
  channel_label: "WhatsApp-compatible simulator",
  preferred_language: "en" as const,
  real_whatsapp_configured: false,
  messages: [],
  pending_submission: null,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ConversationPage", () => {
  it("shows extraction as unrecorded and requires explicit confirmation", async () => {
    const extractedConversation = {
      ...emptyConversation,
      messages: [
        {
          message_id: "message-1",
          direction: "inbound",
          content: "I-BP yami ngu-168 over 105 ngo-11:30.",
          message_type: "patient",
          delivery_status: "delivered",
          created_at: "2026-07-18T09:30:00Z",
        },
        {
          message_id: "message-2",
          direction: "outbound",
          content: "Please check the extracted details and confirm or correct them.",
          message_type: "system",
          delivery_status: "sent",
          created_at: "2026-07-18T09:30:00Z",
        },
      ],
      pending_submission: pending,
    };
    const confirmedConversation = {
      ...extractedConversation,
      pending_submission: null,
      messages: [
        ...extractedConversation.messages,
        {
          message_id: "message-3",
          direction: "outbound",
          content: "Reading confirmed. Your care team has been notified for review.",
          message_type: "system",
          delivery_status: "sent",
          created_at: "2026-07-18T09:31:00Z",
        },
      ],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => emptyConversation })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ conversation: extractedConversation }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ conversation: confirmedConversation }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationPage />);

    expect(await screen.findByText("Send a home BP reading")).toBeInTheDocument();
    expect(screen.getByText("Simulator")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "I-BP yami ngu-168 over 105 ngo-11:30." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("AI-extracted draft · not recorded")).toBeInTheDocument();
    expect(screen.getByText("168 / 105")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm and save" }));

    expect(
      await screen.findByText("Reading confirmed. Your care team has been notified for review."),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("AI-extracted draft · not recorded")).not.toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/patient/conversation/submission-conversation-1/confirm",
      { method: "POST" },
    );
  });
});
