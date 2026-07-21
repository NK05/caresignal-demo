import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({
    service: "caresignal-web",
    status: "ok",
    version: "0.1.0",
  });
}

