import { NextResponse } from "next/server";

const GATEWAY = process.env.GATEWAY_INTERNAL_URL || "http://aurum-gateway:8000";

export async function GET() {
  try {
    const res = await fetch(`${GATEWAY}/status`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({
      direction: "UNKNOWN", action: "HOLD", reason: "no_data",
      updated_at: null, stable_since: null,
    });
  }
}
