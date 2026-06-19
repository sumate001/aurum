"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import dynamic from "next/dynamic";
import { computeOutcomes, type OhlcvPoint, type Signal, type SignalOutcome, type TrendCheck } from "@/components/PriceChart";
import ThinkingPanel from "@/components/ThinkingPanel";

const PriceChart = dynamic(() => import("@/components/PriceChart"), { ssr: false });

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const TF_OPTIONS = ["M15", "H1", "H4"];

// ── helpers ─────────────────────────────────────────────────────────────────

const outcomeLabel: Record<string, string> = { TP2: "TP2 HIT", TP1: "TP1 HIT", SL: "SL HIT", OPEN: "OPEN" };
const outcomeColor: Record<string, string> = {
  TP2:  "bg-emerald-500/20 text-emerald-400 border-emerald-600/40",
  TP1:  "bg-green-500/20  text-green-400  border-green-600/40",
  SL:   "bg-red-500/20    text-red-400    border-red-600/40",
  OPEN: "bg-yellow-500/20 text-yellow-400 border-yellow-600/40",
};

const reasonLabel: Record<string, { text: string; color: string }> = {
  first_signal:           { text: "Signal แรก",               color: "text-blue-400" },
  direction_changed:      { text: "⚡ ทิศทางเปลี่ยน!",        color: "text-yellow-300" },
  confidence_surge:       { text: "↑ Confidence พุ่ง",        color: "text-green-400" },
  new_entry_point:        { text: "↩ Entry ใหม่ (pullback)",   color: "text-cyan-400" },
  periodic_reconfirmation:{ text: "↻ ยืนยันรอบ 4h",           color: "text-gray-400" },
  direction_confirmed:    { text: "✓ ทิศทางเดิม",             color: "text-gray-500" },
  hold:                   { text: "— รอสัญญาณ",               color: "text-gray-600" },
  low_confidence:         { text: "— ข้อมูลไม่เพียงพอ",        color: "text-gray-600" },
  no_data:                { text: "— ยังไม่มีข้อมูล",           color: "text-gray-600" },
};

function statusBadge(status: string) {
  const m: Record<string, string> = {
    PENDING_APPROVAL: "bg-yellow-500/10 text-yellow-500/80 border-yellow-600/30",
    APPROVED:         "bg-blue-500/20   text-blue-400",
    EXECUTED:         "bg-green-500/20  text-green-400",
    REJECTED:         "bg-red-500/20    text-red-400",
    CANCELLED:        "bg-gray-700      text-gray-500",
  };
  return m[status] || "bg-gray-700 text-gray-500";
}

function timeSince(iso: string | null): string {
  if (!iso) return "—";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60)   return `${diff} วินาทีที่แล้ว`;
  if (diff < 3600) return `${Math.floor(diff / 60)} นาทีที่แล้ว`;
  return `${Math.floor(diff / 3600)} ชั่วโมง ${Math.floor((diff % 3600) / 60)} นาทีที่แล้ว`;
}

function pnlText(o: SignalOutcome) {
  return `${o.pnl >= 0 ? "+" : ""}${o.pnl.toFixed(2)}`;
}

function fmtCountdown(sec: number) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function useSecondTick() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return tick;
}

const DATA_REFRESH_SEC  = 15;   // SWR polls every 15s
const ANALYSIS_CYCLE_SEC = 15 * 60; // collector runs every 15 min

// ── Page ────────────────────────────────────────────────────────────────────

export default function Home() {
  const [tf, setTf]             = useState("H1");
  const [activeId, setActiveId] = useState<string | null>(null);

  const { data: signals = [], isValidating: sigLoading }    = useSWR<Signal[]>("/api/signals?limit=30", fetcher, { refreshInterval: 15000 });
  const { data: trendRaw,     isValidating: trendLoading }  = useSWR("/api/status",         fetcher, { refreshInterval: 15000 });
  const { data: calendar }                                   = useSWR("/api/calendar",       fetcher, { refreshInterval: 60000 });
  const { data: ohlcvRes }                                   = useSWR(`/api/ohlcv?tf=${tf}`, fetcher, { refreshInterval: 60000 });
  const { data: trendHistoryRaw = [] }                       = useSWR<TrendCheck[]>("/api/trend-history", fetcher, { refreshInterval: 15000 });

  const tick      = useSecondTick();
  const isFetching = sigLoading || trendLoading;
  const nowSec    = Math.floor(Date.now() / 1000);
  const secUntilDataRefresh   = DATA_REFRESH_SEC  - (nowSec % DATA_REFRESH_SEC);
  const secUntilAnalysisCycle = ANALYSIS_CYCLE_SEC - (nowSec % ANALYSIS_CYCLE_SEC);
  void tick; // consumed via nowSec inside render

  const ohlcv: OhlcvPoint[] = (ohlcvRes?.data ?? []).slice(-60);
  const trend = trendRaw ?? { direction: "UNKNOWN", action: "HOLD", reason: "no_data" };

  const outcomes: SignalOutcome[] = ohlcv.length > 0 ? computeOutcomes(signals, ohlcv) : [];

  const tp1Hits  = outcomes.filter((o) => o.outcome === "TP1" || o.outcome === "TP2").length;
  const slHits   = outcomes.filter((o) => o.outcome === "SL").length;
  const totalPnl = outcomes.reduce((s, o) => s + o.pnl, 0);

  const activeOutcome = activeId
    ? outcomes.find((o) => o.id === activeId)
    : outcomes[0] ?? null;

  const currentPrice = ohlcv.length > 0 ? Number(ohlcv[ohlcv.length - 1].close) : null;

  const dirColor =
    trend.direction === "BULLISH" ? "text-green-400" :
    trend.direction === "BEARISH" ? "text-red-400"   : "text-gray-400";

  const isNewSignal = trend.reason === "direction_changed" || trend.reason === "confidence_surge" || trend.reason === "new_entry_point";
  const agentOutputs: any[] = (signals[0] as any)?.agent_outputs ?? [];
  const reasonInfo = reasonLabel[trend.reason] ?? { text: trend.reason, color: "text-gray-500" };

  return (
    <div className="flex flex-col h-full w-full select-none">

      {/* ── HEADER ──────────────────────────────────────────────────── */}
      <header className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 bg-[#0d1525] shrink-0 flex-wrap">
        <span className="text-yellow-400 font-bold text-lg tracking-wide">AURUM</span>

        {currentPrice && (
          <span className="text-yellow-300 font-bold text-base font-mono">
            {currentPrice.toFixed(2)}
          </span>
        )}

        {/* Trend direction */}
        <div className={`flex items-center gap-1.5 font-semibold text-sm ${dirColor}`}>
          <span className="text-[10px]">●</span>
          {trend.direction}
          {trend.macro_confidence && (
            <span className="font-normal text-xs opacity-60">{trend.macro_confidence}%</span>
          )}
        </div>

        {/* Reason / status */}
        <div className={`text-xs font-medium ${reasonInfo.color}`}>
          {reasonInfo.text}
        </div>

        {isNewSignal && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-yellow-500/20 border border-yellow-500/50 text-yellow-300 text-xs font-bold animate-pulse">
            ⚡ NEW SIGNAL
          </div>
        )}

        {/* Accuracy */}
        {outcomes.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-gray-800/60 border border-gray-700/60 text-xs ml-1">
            <span className="text-gray-500">Signals</span>
            <span className="text-green-400 font-bold">{tp1Hits} TP</span>
            <span className="text-red-400 font-bold">{slHits} SL</span>
            <span className={`font-mono font-bold ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(1)} pts
            </span>
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          {/* Live pulse (always visible) */}
          <span className="relative flex h-2 w-2">
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${isFetching ? "bg-yellow-400" : "bg-green-500"}`} />
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isFetching ? "bg-yellow-400" : "bg-green-500"}`} />
          </span>

          {/* Countdown timers — hidden on small screens */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-[11px]">
            <span className="text-gray-500">{isFetching ? "กำลังดึงข้อมูล…" : "Live"}</span>
            <span className="text-gray-700">|</span>
            <span className="text-gray-500">ข้อมูล</span>
            <span className={`font-mono font-bold tabular-nums ${secUntilDataRefresh <= 3 ? "text-yellow-400" : "text-gray-300"}`}>
              0:{String(secUntilDataRefresh).padStart(2, "0")}
            </span>
            <span className="text-gray-700">|</span>
            <span className="text-gray-500">วิเคราะห์</span>
            <span className={`font-mono font-bold tabular-nums ${secUntilAnalysisCycle <= 30 ? "text-yellow-400" : "text-gray-300"}`}>
              {fmtCountdown(secUntilAnalysisCycle)}
            </span>
          </div>

          {/* TF selector */}
          <div className="flex bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
            {TF_OPTIONS.map((t) => (
              <button key={t} onClick={() => setTf(t)}
                className={`px-2.5 py-1 text-xs font-medium transition-colors ${tf === t ? "bg-yellow-500/20 text-yellow-400" : "text-gray-500 hover:text-gray-300"}`}>
                {t}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ── BODY ────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-hidden">

        {/* CHART */}
        <main className="h-[45%] md:h-auto md:flex-1 shrink-0 min-w-0 flex flex-col border-b md:border-b-0 md:border-r border-gray-800">
          <div className="flex items-center gap-3 px-4 pt-2.5 pb-1 shrink-0 flex-wrap text-[11px]">
            <span className="text-gray-600 font-medium uppercase tracking-wider">GOLD# {tf} · Price vs Signal</span>
            <span className="flex items-center gap-1.5 text-gray-500"><span className="w-3 h-0.5 bg-yellow-500 inline-block rounded" /> Close</span>
            <span className="flex items-center gap-1.5 text-green-400"><span className="w-3 h-3 rounded-sm inline-block bg-green-500/20 border border-green-600/40" /> TP zone</span>
            <span className="flex items-center gap-1.5 text-red-400"><span className="w-3 h-3 rounded-sm inline-block bg-red-500/20 border border-red-600/40" /> SL zone</span>
            <span className="flex items-center gap-1.5 text-yellow-400"><span className="w-3 h-3 rounded-sm inline-block bg-yellow-500/10 border border-yellow-600/30" /> Open</span>
            <span className="flex items-center gap-1.5 text-gray-500"><span className="w-2.5 h-2.5 rounded-full inline-block bg-gray-700 border border-gray-600" /> ตรวจแล้ว / ไม่เปลี่ยน</span>
          </div>
          <div className="flex-1 min-h-0 px-2 pb-2">
            <PriceChart ohlcv={ohlcv} outcomes={outcomes} activeSignal={activeOutcome ?? null} trendHistory={trendHistoryRaw} />
          </div>
        </main>

        {/* RIGHT SIDEBAR */}
        <aside className="flex-1 md:flex-none md:w-72 shrink-0 flex flex-col overflow-y-auto bg-[#0d1525]">

          {/* ── TREND STATUS PANEL ── key info ── */}
          <div className={`px-4 py-3 border-b ${isNewSignal ? "border-yellow-700/50 bg-yellow-500/5" : "border-gray-800"}`}>
            <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-gray-600 uppercase tracking-widest">สถานะทิศทางตลาด</span>
            {/* Mini analysis cycle progress bar */}
            <div className="flex items-center gap-1.5">
              <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-yellow-500/60 rounded-full transition-all duration-1000"
                  style={{ width: `${100 - (secUntilAnalysisCycle / ANALYSIS_CYCLE_SEC) * 100}%` }}
                />
              </div>
              <span className="text-[9px] font-mono text-gray-600">{fmtCountdown(secUntilAnalysisCycle)}</span>
            </div>
          </div>

            <div className={`text-2xl font-bold mb-1 ${dirColor}`}>{trend.direction}</div>

            <div className={`text-xs font-semibold mb-3 ${reasonInfo.color}`}>{reasonInfo.text}</div>

            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-600">ทิศทางคงเสถียรมา</span>
                <span className="text-gray-300 font-medium">{timeSince(trend.stable_since)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">อัปเดตล่าสุด</span>
                <span className="text-gray-400">{timeSince(trend.updated_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Macro confidence</span>
                <span className="text-gray-300">{trend.macro_confidence ?? "—"}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Technical</span>
                <span className="text-gray-300">{trend.technical_consensus || "—"}</span>
              </div>
            </div>

            {/* Setup type */}
            {trend.setup_type && (
              <div className="mt-2 px-2 py-1.5 rounded-lg bg-gray-900 border border-gray-700 text-[10px] text-gray-400">
                {trend.setup_type}
              </div>
            )}

            {/* What to do */}
            <div className={`mt-2 p-2.5 rounded-lg text-xs leading-relaxed ${
              isNewSignal
                ? "bg-yellow-500/10 border border-yellow-600/40 text-yellow-200"
                : trend.action === "HOLD"
                ? "bg-gray-800 text-gray-500"
                : "bg-gray-800/60 text-gray-400"
            }`}>
              {isNewSignal ? (
                <>⚡ มี signal ใหม่เข้ามา ควรพิจารณา {trend.action} ที่ {trend.entry?.toFixed(2)}</>
              ) : trend.action === "HOLD" || trend.direction === "NEUTRAL" ? (
                <>{trend.setup_type || "รอ setup ที่ถูกต้อง"}</>
              ) : (
                <>ทิศทาง {trend.direction} ยังคงเดิม — ไม่มี signal ใหม่</>
              )}
            </div>

            {/* Daily signal counter */}
            {trend.max_daily_signals != null && (
              <div className="mt-2 flex justify-between text-[10px] text-gray-600">
                <span>Signal วันนี้</span>
                <span className={trend.daily_signals_sent >= trend.max_daily_signals ? "text-red-500" : "text-gray-400"}>
                  {trend.daily_signals_sent ?? 0} / {trend.max_daily_signals}
                </span>
              </div>
            )}

            {/* Session */}
            {trend.session !== undefined && (
              <div className="mt-1 flex justify-between text-[10px] text-gray-600">
                <span>Session</span>
                <span className={trend.session ? "text-green-600" : "text-gray-700"}>
                  {trend.session ? trend.session.toUpperCase() : "OFF HOURS"}
                </span>
              </div>
            )}
          </div>

          {/* Active signal detail */}
          {activeOutcome && (
            <div className="px-4 py-3 border-b border-gray-800">
              <div className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">Signal ที่เลือก</div>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-xl font-bold ${activeOutcome.action === "BUY" ? "text-green-400" : "text-red-400"}`}>
                  {activeOutcome.action}
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border ${outcomeColor[activeOutcome.outcome]}`}>
                  {outcomeLabel[activeOutcome.outcome]}
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                {[
                  { label: "Entry", val: activeOutcome.entry, color: "text-yellow-400" },
                  { label: "SL",    val: activeOutcome.sl,    color: "text-red-400"    },
                  { label: "TP1",   val: activeOutcome.tp1,   color: "text-green-400"  },
                  { label: "TP2",   val: activeOutcome.tp2,   color: "text-green-600"  },
                ].map(({ label, val, color }) =>
                  val ? (
                    <div key={label} className="flex justify-between">
                      <span className="text-gray-600">{label}</span>
                      <span className={`font-mono font-semibold ${color}`}>{val.toFixed(2)}</span>
                    </div>
                  ) : null
                )}
                <div className="flex justify-between pt-1.5 border-t border-gray-800">
                  <span className="text-gray-600">R:R (TP1)</span>
                  <span className="text-gray-300 font-mono">
                    {activeOutcome.entry && activeOutcome.sl && activeOutcome.tp1
                      ? (Math.abs(activeOutcome.tp1 - activeOutcome.entry) / Math.abs(activeOutcome.entry - activeOutcome.sl)).toFixed(2)
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">PnL {activeOutcome.outcome === "OPEN" ? "(unrealised)" : "(realised)"}</span>
                  <span className={`font-mono font-bold ${activeOutcome.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {pnlText(activeOutcome)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Technical agents */}
          {agentOutputs.length > 0 && (
            <div className="px-4 py-3 border-b border-gray-800">
              <div className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">Technical Agents</div>
              <div className="space-y-1.5">
                {agentOutputs.map((ag: any) => {
                  const dot = ag.signal === "BUY" ? "bg-green-500" : ag.signal === "SELL" ? "bg-red-500" : "bg-gray-600";
                  const txt = ag.signal === "BUY" ? "text-green-400" : ag.signal === "SELL" ? "text-red-400" : "text-gray-500";
                  return (
                    <div key={ag.agent_name} className="flex items-center gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${dot} shrink-0`} />
                      <span className="text-xs text-gray-400 flex-1 truncate">{ag.agent_name}</span>
                      <span className={`text-xs font-semibold ${txt}`}>{ag.signal}</span>
                      <span className="text-xs text-gray-600 w-14 text-right font-mono">
                        {typeof ag.value === "number" ? ag.value.toFixed(2) : "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Calendar */}
          <div className="px-4 py-3">
            <div className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">Economic Calendar</div>
            {(calendar?.events ?? []).length === 0 ? (
              <p className="text-xs text-gray-600">No upcoming high-impact events</p>
            ) : (
              <div className="space-y-2">
                {(calendar.events as any[]).slice(0, 5).map((ev: any, i: number) => (
                  <div key={i} className="text-xs">
                    <div className="text-gray-300 font-medium truncate">{ev.event_name || ev.title}</div>
                    <div className="text-gray-600">{ev.currency} · {ev.impact}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* ── AI THINKING ─────────────────────────────────────────── */}
      <ThinkingPanel signal={signals[0]} />

      {/* ── SIGNAL HISTORY (only real signals, not every cycle) ──── */}
      <div className="shrink-0 border-t border-gray-800 bg-[#0d1525] max-h-[28%] md:max-h-none flex flex-col">
        <div className="px-4 py-2 flex items-center gap-3 border-b border-gray-800/50">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">Signal History</span>
          <span className="hidden sm:inline text-[10px] text-gray-700">
            {signals.length} signals (เฉพาะเมื่อทิศทางเปลี่ยน / pullback / reconfirm 4h)
          </span>
        </div>
        <div
          className="flex gap-3 overflow-x-auto px-4 py-3 touch-pan-x flex-1 min-h-0"
          style={{ scrollbarWidth: "thin", scrollbarColor: "#374151 transparent", WebkitOverflowScrolling: "touch" } as React.CSSProperties}
        >
          {outcomes.length === 0 ? (
            <p className="text-xs text-gray-600 py-1">ยังไม่มี signal — รอวิเคราะห์รอบหน้า…</p>
          ) : (
            outcomes.map((o) => {
              const isActive = o.id === activeOutcome?.id;
              const border = o.action === "BUY" ? "border-green-800" : "border-red-800";
              return (
                <button key={o.id} onClick={() => setActiveId(isActive ? null : o.id)}
                  className={`shrink-0 rounded-xl border p-3 text-left text-xs transition-all min-w-[160px] active:scale-95 ${border}
                    ${isActive ? "bg-gray-800 ring-1 ring-yellow-500/50" : "bg-[#111827] hover:bg-gray-800/50"}`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={`font-bold text-sm ${o.action === "BUY" ? "text-green-400" : "text-red-400"}`}>
                      {o.action}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${outcomeColor[o.outcome]}`}>
                      {outcomeLabel[o.outcome]}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline mb-1">
                    <span className="text-gray-500 text-[10px]">Entry</span>
                    <span className="font-mono text-gray-200">{o.entry?.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-[10px] mb-2">
                    <span className="text-red-400">{o.sl?.toFixed(2)}</span>
                    <span className="text-gray-600">↕</span>
                    <span className="text-green-400">{o.tp1?.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600 text-[10px]" title={`Signal: ${new Date(o.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`}>
                      Bar: {new Date(o.signalBarDatetime).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <span className={`font-mono font-bold ${o.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {pnlText(o)}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
