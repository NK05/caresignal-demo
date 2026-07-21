import { NextResponse } from "next/server";

const patientId = process.env.CARESIGNAL_DEMO_PATIENT_USER_ID ?? "10000000-0000-4000-8000-000000000001";
const apiBase = (process.env.CARESIGNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

export async function POST(_request: Request, context: { params: Promise<{ submissionId: string; action: string }> }) {
  const { submissionId, action } = await context.params;
  if (!new Set(["confirm", "reject"]).has(action)) return NextResponse.json({ detail: "Unsupported action" }, { status: 404 });
  try {
    const response = await fetch(`${apiBase}/patient/submissions/${encodeURIComponent(submissionId)}/${action}`, {
      method: "POST",
      headers: { "X-Demo-Session": patientId },
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Cannot reach the CareSignal API." }, { status: 503 });
  }
}
