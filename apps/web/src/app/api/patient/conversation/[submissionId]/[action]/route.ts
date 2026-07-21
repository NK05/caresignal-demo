import { NextResponse } from "next/server";

const apiBase = process.env.CARESIGNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const patientId =
  process.env.CARESIGNAL_DEMO_CONVERSATION_PATIENT_USER_ID ??
  "10000000-0000-4000-8000-000000000002";

export async function POST(
  _request: Request,
  context: { params: Promise<{ submissionId: string; action: string }> },
) {
  const { submissionId, action } = await context.params;
  if (!["confirm", "cancel"].includes(action)) {
    return NextResponse.json({ detail: "Unsupported conversation action." }, { status: 400 });
  }
  try {
    const response = await fetch(
      `${apiBase}/patient/conversation/submissions/${encodeURIComponent(submissionId)}/${action}`,
      {
        method: "POST",
        cache: "no-store",
        headers: { Accept: "application/json", "X-Demo-Session": patientId },
      },
    );
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Cannot complete the synthetic conversation action." },
      { status: 503 },
    );
  }
}
