"use client";

import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

export interface OhlcvPoint {
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Signal {
  id: string;
  created_at: string;
  action: string;
  entry: number;
  sl: number;
  tp1: number;
  tp2: number;
  confidence: number;
  status: string;
  macro_bias?: string;
  macro_confidence?: number;
  timeframe?: string;
  reasoning?: string;
  technical_consensus?: string;
  agent_outputs?: any[];
  raw_macro?: any;
  raw_technical?: any;
  symbol?: string;
}

export interface SignalOutcome extends Signal {
  outcome: "TP2" | "TP1" | "SL" | "OPEN";
  pnl: number;
  signalBarDatetime: string;  // bar ที่ "ครอบ" เวลา signal (bar open ≤ signal time)
  hitDatetime?: string;
}

export interface TrendCheck {
  checked_at: string;
  direction: string;
  action: string;
  confidence: number;
  sent_signal: boolean;
  reason: string;
}

// ── Outcome computation ────────────────────────────────────────────────────

/** หา bar ที่ "ครอบ" เวลา signal: bar ที่เปิดก่อน signal แต่ยังไม่ถึง bar ถัดไป */
function findContainingBarIdx(ohlcv: OhlcvPoint[], sigMs: number): number {
  let idx = 0;
  for (let i = 0; i < ohlcv.length; i++) {
    if (new Date(ohlcv[i].datetime).getTime() <= sigMs) idx = i;
    else break;
  }
  return idx;
}

export function computeOutcomes(signals: Signal[], ohlcv: OhlcvPoint[]): SignalOutcome[] {
  return signals.map((sig) => {
    const sigMs = new Date(sig.created_at).getTime();

    const containingIdx = findContainingBarIdx(ohlcv, sigMs);
    const signalBarDatetime = ohlcv[containingIdx]?.datetime ?? sig.created_at;

    const barsAfter = ohlcv.slice(containingIdx + 1); // bars AFTER signal bar
    const lastClose = ohlcv.length
      ? Number(ohlcv[ohlcv.length - 1].close)
      : sig.entry;

    for (const bar of barsAfter) {
      const h = Number(bar.high);
      const l = Number(bar.low);
      if (sig.action === "BUY") {
        if (sig.tp2 && h >= sig.tp2) return { ...sig, outcome: "TP2", hitDatetime: bar.datetime, pnl: sig.tp2 - sig.entry, signalBarDatetime };
        if (sig.tp1 && h >= sig.tp1) return { ...sig, outcome: "TP1", hitDatetime: bar.datetime, pnl: sig.tp1 - sig.entry, signalBarDatetime };
        if (sig.sl  && l <= sig.sl)  return { ...sig, outcome: "SL",  hitDatetime: bar.datetime, pnl: sig.sl  - sig.entry, signalBarDatetime };
      } else if (sig.action === "SELL") {
        if (sig.tp2 && l <= sig.tp2) return { ...sig, outcome: "TP2", hitDatetime: bar.datetime, pnl: sig.entry - sig.tp2, signalBarDatetime };
        if (sig.tp1 && l <= sig.tp1) return { ...sig, outcome: "TP1", hitDatetime: bar.datetime, pnl: sig.entry - sig.tp1, signalBarDatetime };
        if (sig.sl  && h >= sig.sl)  return { ...sig, outcome: "SL",  hitDatetime: bar.datetime, pnl: sig.entry - sig.sl,  signalBarDatetime };
      }
    }

    const unrealised = sig.action === "BUY" ? lastClose - sig.entry : sig.entry - lastClose;
    return { ...sig, outcome: "OPEN", pnl: unrealised, signalBarDatetime };
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────

function fmtTime(str: string) {
  const d = new Date(str);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// ── Custom renderers ───────────────────────────────────────────────────────

/** ลูกศร signal จริง (ทิศทางเปลี่ยน / entry ใหม่) */
const SignalDot = (props: any) => {
  const { cx, cy, payload } = props;
  if (!payload.sigAction) return null;
  const isBuy = payload.sigAction === "BUY";
  return (
    <g>
      <circle cx={cx} cy={cy} r={11} fill={isBuy ? "#22c55e" : "#ef4444"} stroke="#0a0f1e" strokeWidth={2} />
      <text x={cx} y={cy + 4} textAnchor="middle" fill="#fff" fontSize={12} fontWeight="bold">
        {isBuy ? "▲" : "▼"}
      </text>
    </g>
  );
};

/** จุดเล็กสีเทา — วิเคราะห์แล้ว ทิศทางไม่เปลี่ยน */
const CheckDot = (props: any) => {
  const { cx, cy, payload } = props;
  if (!payload.checkDir) return null;
  const color = payload.checkDir === "BULLISH" ? "#166534" : payload.checkDir === "BEARISH" ? "#7f1d1d" : "#374151";
  return (
    <g>
      <circle cx={cx} cy={cy} r={4} fill={color} stroke="#0a0f1e" strokeWidth={1} opacity={0.85} />
    </g>
  );
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="bg-[#0d1525] border border-gray-700 rounded-xl px-3 py-2.5 text-xs shadow-2xl min-w-[170px]">
      <div className="text-gray-500 mb-1.5">{fmtTime(label)}</div>
      <div className="text-yellow-400 font-bold text-base mb-1">{Number(d.close).toFixed(2)}</div>
      <div className="grid grid-cols-2 gap-x-3 text-gray-500 mb-1">
        <span>O: <span className="text-gray-300">{Number(d.open).toFixed(2)}</span></span>
        <span>H: <span className="text-green-400">{Number(d.high).toFixed(2)}</span></span>
        <span>L: <span className="text-red-400">{Number(d.low).toFixed(2)}</span></span>
      </div>
      {d.sigAction && (
        <div className={`pt-1.5 border-t border-gray-700 font-semibold ${d.sigAction === "BUY" ? "text-green-400" : "text-red-400"}`}>
          ▲ Signal: {d.sigAction} ({d.sigConf}%)
        </div>
      )}
      {d.checkDir && !d.sigAction && (
        <div className="pt-1.5 border-t border-gray-700 text-gray-500">
          ✓ ตรวจแล้ว: {d.checkDir}<br />
          ทิศทางไม่เปลี่ยน ({d.checkConf}%)
        </div>
      )}
    </div>
  );
};

// ── Component ──────────────────────────────────────────────────────────────

interface Props {
  ohlcv: OhlcvPoint[];
  outcomes: SignalOutcome[];
  activeSignal: Signal | null;
  trendHistory?: TrendCheck[];
}

export default function PriceChart({ ohlcv, outcomes, activeSignal, trendHistory = [] }: Props) {
  if (!ohlcv || ohlcv.length === 0) {
    return <div className="flex items-center justify-center h-full text-gray-600 text-sm">Loading price data…</div>;
  }

  // ── Enrich bars ────────────────────────────────────────────────────────

  // Map signal outcomes to their containing bar (exact datetime match)
  const sigByBar = new Map<string, SignalOutcome>();
  for (const o of outcomes) {
    if (!sigByBar.has(o.signalBarDatetime)) sigByBar.set(o.signalBarDatetime, o);
  }

  // Map trend-check (no signal) to nearest bar
  const checkByBar = new Map<string, TrendCheck>();
  for (const tc of trendHistory) {
    if (tc.sent_signal) continue; // signal bar already handled above
    const tcMs = new Date(tc.checked_at).getTime();
    const idx = findContainingBarIdx(ohlcv, tcMs);
    const barDt = ohlcv[idx]?.datetime;
    if (barDt && !sigByBar.has(barDt) && !checkByBar.has(barDt)) {
      checkByBar.set(barDt, tc);
    }
  }

  const chartData = ohlcv.map((pt) => {
    const sig   = sigByBar.get(pt.datetime);
    const check = checkByBar.get(pt.datetime);
    return {
      ...pt,
      close:  Number(pt.close),
      open:   Number(pt.open),
      high:   Number(pt.high),
      low:    Number(pt.low),
      // signal arrow layer
      sigDot:    sig   ? Number(pt.close) : undefined,
      sigAction: sig?.action,
      sigConf:   sig?.confidence,
      // trend-check dot layer (ราคาปลาย bar ไว้วางจุด)
      checkDot:  check ? Number(pt.close) : undefined,
      checkDir:  check?.direction,
      checkConf: check?.confidence,
    };
  });

  // ── Y domain ──────────────────────────────────────────────────────────
  const allLevels = [
    ...chartData.map((d) => d.close),
    ...outcomes.flatMap((o) => [o.entry, o.sl, o.tp1, o.tp2].filter(Boolean) as number[]),
    ...(activeSignal ? [activeSignal.sl, activeSignal.tp1, activeSignal.tp2, activeSignal.entry].filter(Boolean) as number[] : []),
  ];
  const pad = (Math.max(...allLevels) - Math.min(...allLevels)) * 0.06;
  const domainMin = Math.floor(Math.min(...allLevels) - pad);
  const domainMax = Math.ceil(Math.max(...allLevels) + pad);

  const tickInterval = Math.max(1, Math.floor(ohlcv.length / 8));

  const zoneColor:   Record<string, string> = { TP2: "#22c55e", TP1: "#4ade80", SL: "#ef4444", OPEN: "#eab308" };
  const zoneOpacity: Record<string, number> = { TP2: 0.12, TP1: 0.09, SL: 0.10, OPEN: 0.05 };
  const lastDatetime = ohlcv[ohlcv.length - 1]?.datetime;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={chartData} margin={{ top: 12, right: 12, bottom: 8, left: 0 }}>
        <defs>
          <linearGradient id="goldGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#EAB308" stopOpacity={0.18} />
            <stop offset="80%" stopColor="#EAB308" stopOpacity={0} />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="2 4" stroke="#1a2333" vertical={false} />

        <XAxis dataKey="datetime" tickFormatter={fmtTime}
          tick={{ fill: "#4b5563", fontSize: 11 }} axisLine={false} tickLine={false} interval={tickInterval} />
        <YAxis domain={[domainMin, domainMax]} tickFormatter={(v) => v.toFixed(0)}
          tick={{ fill: "#4b5563", fontSize: 11 }} axisLine={false} tickLine={false} width={64} orientation="right" />

        <Tooltip content={<CustomTooltip />} />

        {/* Outcome zones */}
        {outcomes.map((o) => (
          <ReferenceArea key={o.id}
            x1={o.signalBarDatetime} x2={o.hitDatetime ?? lastDatetime}
            fill={zoneColor[o.outcome]} fillOpacity={zoneOpacity[o.outcome]}
            ifOverflow="extendDomain" />
        ))}

        {/* Price area */}
        <Area dataKey="close" stroke="#EAB308" strokeWidth={1.8} fill="url(#goldGrad)"
          dot={false} activeDot={false} isAnimationActive={false} />

        {/* Trend-check dots (วิเคราะห์แล้ว ทิศทางไม่เปลี่ยน) */}
        <Line dataKey="checkDot" stroke="transparent"
          dot={<CheckDot />} activeDot={false} isAnimationActive={false} legendType="none" />

        {/* Signal arrows (ทิศทางเปลี่ยน / entry ใหม่) */}
        <Line dataKey="sigDot" stroke="transparent"
          dot={<SignalDot />} activeDot={false} isAnimationActive={false} legendType="none" />

        {/* All signal entry lines (faint) */}
        {outcomes.map((o) => (
          <ReferenceLine key={`e-${o.id}`} y={o.entry}
            stroke={o.action === "BUY" ? "#22c55e" : "#ef4444"}
            strokeOpacity={0.2} strokeWidth={1} strokeDasharray="2 4" />
        ))}

        {/* Active signal lines (prominent) */}
        {activeSignal?.entry && (
          <ReferenceLine y={activeSignal.entry} stroke="#EAB308" strokeDasharray="6 3" strokeWidth={2}
            label={{ value: `Entry ${activeSignal.entry.toFixed(2)}`, position: "insideLeft", fill: "#EAB308", fontSize: 10, dx: 4 }} />
        )}
        {activeSignal?.sl && (
          <ReferenceLine y={activeSignal.sl} stroke="#ef4444" strokeDasharray="6 3" strokeWidth={2}
            label={{ value: `SL ${activeSignal.sl.toFixed(2)}`, position: "insideLeft", fill: "#ef4444", fontSize: 10, dx: 4 }} />
        )}
        {activeSignal?.tp1 && (
          <ReferenceLine y={activeSignal.tp1} stroke="#22c55e" strokeDasharray="6 3" strokeWidth={2}
            label={{ value: `TP1 ${activeSignal.tp1.toFixed(2)}`, position: "insideLeft", fill: "#22c55e", fontSize: 10, dx: 4 }} />
        )}
        {activeSignal?.tp2 && (
          <ReferenceLine y={activeSignal.tp2} stroke="#16a34a" strokeDasharray="4 4" strokeWidth={1.5}
            label={{ value: `TP2 ${activeSignal.tp2.toFixed(2)}`, position: "insideLeft", fill: "#16a34a", fontSize: 10, dx: 4 }} />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
