import { NextResponse } from "next/server";

const patientId = process.env.CARESIGNAL_DEMO_PATIENT_USER_ID ?? "10000000-0000-4000-8000-000000000001";
const apiBase = (process.env.CARESIGNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const headers = { Accept: "application/json", "X-Demo-Session": patientId };
    const responses = await Promise.all([
      fetch(`${apiBase}/patient/profile`, { cache: "no-store", headers }),
      fetch(`${apiBase}/patient/readings`, { cache: "no-store", headers }),
      fetch(`${apiBase}/patient/follow-up`, { cache: "no-store", headers }),
    ]);
    if (responses.some((response) => !response.ok)) throw new Error("Patient API unavailable");
    const [profile, readings, follow_up] = await Promise.all(responses.map((response) => response.json()));
    return NextResponse.json({ profile, readings, follow_up });
  } catch {
    return NextResponse.json({ detail: "Cannot load the synthetic patient workspace." }, { status: 503 });
  }
}
