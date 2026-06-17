import { NextResponse } from "next/server";

const GATEWAY = process.env.GATEWAY_INTERNAL_URL || "http://aurum-gateway:8000";

export async function GET() {
  try {
    const res = await fetch(`${GATEWAY}/trend-history?limit=100`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json([]);
  }
}
