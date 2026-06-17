import { NextRequest, NextResponse } from "next/server";

const GATEWAY = process.env.GATEWAY_INTERNAL_URL || "http://aurum-gateway:8000";

export async function GET(req: NextRequest) {
  const limit = req.nextUrl.searchParams.get("limit") || "20";
  try {
    const res = await fetch(`${GATEWAY}/signals?limit=${limit}`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json([], { status: 200 });
  }
}
