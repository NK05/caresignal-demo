import { NextResponse } from "next/server";

const defaultClinicianUserId = "20000000-0000-4000-8000-000000000001";

export const dynamic = "force-dynamic";

export async function GET() {
  const apiBaseUrl = (process.env.CARESIGNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");
  const clinicianUserId = process.env.CARESIGNAL_DEMO_CLINICIAN_USER_ID ?? defaultClinicianUserId;

  try {
    const response = await fetch(`${apiBaseUrl}/clinician/dashboard`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "X-Demo-Session": clinicianUserId,
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { detail: "The synthetic clinician workspace is temporarily unavailable." },
        { status: response.status },
      );
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json(
      { detail: "Cannot reach the CareSignal API. Check the local API service and try again." },
      { status: 503 },
    );
  }
}
