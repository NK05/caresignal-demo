import { NextRequest, NextResponse } from "next/server";

const apiBase = process.env.CARESIGNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const patientId =
  process.env.CARESIGNAL_DEMO_CONVERSATION_PATIENT_USER_ID ??
  "10000000-0000-4000-8000-000000000002";

const headers = {
  Accept: "application/json",
  "Content-Type": "application/json",
  "X-Demo-Session": patientId,
};

export async function GET() {
  try {
    const response = await fetch(`${apiBase}/patient/conversation`, {
      cache: "no-store",
      headers,
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Cannot load the synthetic conversation." },
      { status: 503 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json();
    const response = await fetch(`${apiBase}/patient/conversation/messages`, {
      method: "POST",
      cache: "no-store",
      headers,
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Cannot send the synthetic conversation message." },
      { status: 503 },
    );
  }
}
