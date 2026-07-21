import { NextResponse } from "next/server";

const patientId = process.env.CARESIGNAL_DEMO_PATIENT_USER_ID ?? "10000000-0000-4000-8000-000000000001";
const apiBase = (process.env.CARESIGNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

export async function POST(request: Request) {
  try {
    const response = await fetch(`${apiBase}/patient/submissions/structured`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Demo-Session": patientId },
      body: await request.text(),
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Cannot reach the CareSignal API." }, { status: 503 });
  }
}
