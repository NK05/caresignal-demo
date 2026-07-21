import { NextResponse } from "next/server";

const defaultClinicianUserId = "20000000-0000-4000-8000-000000000001";
const supportedActions = new Set([
  "assign",
  "acknowledge",
  "start-review",
  "contact-attempts",
  "draft-message",
  "ai-draft-message",
  "case-brief",
  "approve-message",
  "resolve",
  "reopen",
]);

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  context: { params: Promise<{ taskId: string; action: string }> },
) {
  const { taskId, action } = await context.params;
  if (!supportedActions.has(action)) {
    return NextResponse.json({ detail: "Unsupported clinician task action." }, { status: 404 });
  }

  const apiBaseUrl = (process.env.CARESIGNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(
    /\/$/,
    "",
  );
  const clinicianUserId =
    process.env.CARESIGNAL_DEMO_CLINICIAN_USER_ID ?? defaultClinicianUserId;
  const requestBody = await request.text();

  try {
    const response = await fetch(
      `${apiBaseUrl}/clinician/tasks/${encodeURIComponent(taskId)}/${action}`,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(requestBody ? { "Content-Type": "application/json" } : {}),
          "X-Demo-Session": clinicianUserId,
        },
        ...(requestBody ? { body: requestBody } : {}),
      },
    );
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json(
        { detail: body.detail ?? "The clinician task action could not be completed." },
        { status: response.status },
      );
    }
    return NextResponse.json(body);
  } catch {
    return NextResponse.json(
      { detail: "Cannot reach the CareSignal API. Check the local API service and try again." },
      { status: 503 },
    );
  }
}
