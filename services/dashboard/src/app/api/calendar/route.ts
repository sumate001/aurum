import { NextResponse } from "next/server";

const FF_SCRAPER = process.env.FF_SCRAPER_INTERNAL_URL || "http://aurum-ff-scraper:5000";

export async function GET() {
  try {
    const res = await fetch(`${FF_SCRAPER}/api/calendar`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ events: [] }, { status: 200 });
  }
}
