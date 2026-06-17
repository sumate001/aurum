import { NextRequest, NextResponse } from "next/server";

const SIGNAL = process.env.SIGNAL_INTERNAL_URL || "http://aurum-signal:8000";

export async function GET(req: NextRequest) {
  const tf = req.nextUrl.searchParams.get("tf") || "H1";
  const symbol = req.nextUrl.searchParams.get("symbol") || "GOLD%23";
  try {
    const res = await fetch(`${SIGNAL}/ohlcv?symbol=${symbol}&tf=${tf}`, {
      cache: "no-store",
      next: { revalidate: 0 },
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ symbol: "GOLD#", tf, data: [] });
  }
}
