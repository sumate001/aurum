"use client";

import { useEffect, useRef, useState, useMemo } from "react";

interface ThinkingMessage {
  speaker: string;
  tag: string;
  text: string;
  speakerColor: string;
  textColor: string;
}

const PERSONA_STYLE: Record<string, { tag: string; speakerColor: string; textColor: string }> = {
  "ADHD":                { tag: "⚡ ADHD",      speakerColor: "text-amber-400",  textColor: "text-amber-200/80"  },
  "Central Bank Buyer":  { tag: "CENTRAL BANK", speakerColor: "text-blue-400",   textColor: "text-blue-100/70"   },
  "Hedge Fund Manager":  { tag: "HEDGE FUND",   speakerColor: "text-violet-400", textColor: "text-violet-100/70" },
  "Retail Trader Long":  { tag: "RETAIL LONG",  speakerColor: "text-green-400",  textColor: "text-green-100/70"  },
  "Retail Trader Short": { tag: "RETAIL SHORT", speakerColor: "text-red-400",    textColor: "text-red-100/70"    },
  "Market Maker":        { tag: "MKT MAKER",    speakerColor: "text-orange-400", textColor: "text-orange-100/70" },
  "Macro Analyst":       { tag: "MACRO",        speakerColor: "text-cyan-400",   textColor: "text-cyan-100/70"   },
  "ORCHESTRATOR":        { tag: "ORCHESTRATOR", speakerColor: "text-white",      textColor: "text-gray-100/90"   },
};

const DEMO_MESSAGES: ThinkingMessage[] = [
  { speaker: "ADHD",                tag: "⚡ ADHD",      speakerColor: "text-amber-400",  textColor: "text-amber-200/80",  text: "[BEARISH ~28%] Fed dovish pivot may be a tactical hedge against Treasury refunding stress — once CPI reveals sticky core services, real rates spike and gold sells off despite DXY weakness.  →trigger: 10Y breakeven drops while real yields break +1.45%" },
  { speaker: "Central Bank Buyer",  tag: "CENTRAL BANK", speakerColor: "text-blue-400",   textColor: "text-blue-100/70",   text: "BULLISH 75% — Strategic accumulation thesis intact. DXY weakness and Fed pivot align with long-term reserve diversification. CPI will create dip-buying opportunity; ignoring short-term gamma noise." },
  { speaker: "Hedge Fund Manager",  tag: "HEDGE FUND",   speakerColor: "text-violet-400", textColor: "text-violet-100/70", text: "NEUTRAL 60% — Momentum intact but entering binary CPI event with diminishing risk/reward. Monitoring DXY and real yields as potential reversal triggers. Standing aside pre-data." },
  { speaker: "ADHD",                tag: "⚡ ADHD",      speakerColor: "text-amber-400",  textColor: "text-amber-200/80",  text: "[NEUTRAL ~20%] Current rally is dealer-driven gamma-chasing, not spot demand. CPI volatility will create a delta-hedging wedge that caps upside and triggers mean reversion." },
  { speaker: "Market Maker",        tag: "MKT MAKER",    speakerColor: "text-orange-400", textColor: "text-orange-100/70", text: "NEUTRAL 85% — No directional bias. Focusing on liquidity sweeps above 3310 and stop clusters below 3270. Will fade extremes and hunt stops rather than commit to trend." },
  { speaker: "Macro Analyst",       tag: "MACRO",        speakerColor: "text-cyan-400",   textColor: "text-cyan-100/70",   text: "BULLISH 80% — Anchored in long-term DXY inverse correlation and monetary easing cycle. CPI viewed as transient volatility. Physical and ETF flows support structural higher floor." },
  { speaker: "Retail Trader Short", tag: "RETAIL SHORT", speakerColor: "text-red-400",    textColor: "text-red-100/70",    text: "BEARISH 70% — Fading rally into 3290 resistance ahead of CPI. Expecting sticky core services and capital flight to short T-bills. Tight stops above 3300." },
  { speaker: "ORCHESTRATOR",        tag: "ORCHESTRATOR", speakerColor: "text-white",      textColor: "text-gray-100/90",   text: "Structural drivers dominate. Fed pivot expectations and DXY weakness create tactical post-data dip-buying opportunity. Signal favors H1 entry on initial volatility digestion toward structural reversion." },
];

function buildMessages(signal: any): ThinkingMessage[] {
  const msgs: ThinkingMessage[] = [];
  const raw = signal?.raw_macro?.raw_output ?? signal?.raw_macro;
  if (!raw) return DEMO_MESSAGES;

  for (const h of (raw.adhd_hypotheses ?? [])) {
    const style = PERSONA_STYLE["ADHD"];
    msgs.push({
      speaker: "ADHD",
      tag: style.tag,
      text: `[${h.direction} ~${h.probability}%] ${h.hypothesis}${h.key_trigger ? `  →trigger: ${h.key_trigger}` : ""}`,
      speakerColor: style.speakerColor,
      textColor: style.textColor,
    });
  }

  for (const v of (raw.votes ?? [])) {
    if (!v.reasoning || v.reasoning === "fallback") continue;
    const style = PERSONA_STYLE[v.persona] ?? { tag: v.persona, speakerColor: "text-gray-300", textColor: "text-gray-400/80" };
    msgs.push({
      speaker: v.persona,
      tag: style.tag,
      text: `${v.direction} ${v.confidence}% — ${v.reasoning}`,
      speakerColor: style.speakerColor,
      textColor: style.textColor,
    });
  }

  if (signal?.reasoning) {
    const style = PERSONA_STYLE["ORCHESTRATOR"];
    msgs.push({
      speaker: "ORCHESTRATOR",
      tag: style.tag,
      text: signal.reasoning,
      speakerColor: style.speakerColor,
      textColor: style.textColor,
    });
  }

  return msgs.length ? msgs : DEMO_MESSAGES;
}

const CHAR_MS   = 14;
const PAUSE_MS  = 2200;
const MAX_LOG   = 18;
const MAX_CHARS = 280;

export default function ThinkingPanel({ signal }: { signal: any }) {
  const messages = useMemo(() => buildMessages(signal), [signal]);

  const [log,         setLog]         = useState<ThinkingMessage[]>([]);
  const [currentIdx,  setCurrentIdx]  = useState(0);
  const [charIdx,     setCharIdx]     = useState(0);
  const [currentText, setCurrentText] = useState("");
  const [pausing,     setPausing]     = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!messages.length || pausing) return;
    const msg  = messages[currentIdx % messages.length];
    const full = msg.text.slice(0, MAX_CHARS);

    if (charIdx < full.length) {
      const id = setTimeout(() => {
        setCurrentText(full.slice(0, charIdx + 1));
        setCharIdx(c => c + 1);
      }, CHAR_MS);
      return () => clearTimeout(id);
    }

    setPausing(true);
    const id = setTimeout(() => {
      setLog(prev => [...prev.slice(-(MAX_LOG - 1)), { ...msg, text: full }]);
      setCurrentText("");
      setCharIdx(0);
      setCurrentIdx(i => i + 1);
      setPausing(false);
    }, PAUSE_MS);
    return () => clearTimeout(id);
  }, [charIdx, currentIdx, messages, pausing]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log, currentText]);

  const current = messages[currentIdx % messages.length];

  return (
    <div
      className="shrink-0 border-t border-gray-800/80 flex flex-col overflow-hidden select-none"
      style={{
        height: 128,
        background: "linear-gradient(180deg,#03070f 0%,#020509 100%)",
      }}
    >
      {/* Header bar */}
      <div className="flex items-center gap-2.5 px-4 py-1 border-b border-gray-800/60 bg-black/30 shrink-0">
        <span className="text-[9px] text-gray-600 tracking-[0.2em] uppercase font-semibold">AI Thinking</span>
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75 animate-ping" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green-500" />
        </span>
        <span className={`text-[9px] font-mono font-semibold ${current.speakerColor}`}>
          {current.tag}
        </span>
        <div className="ml-auto flex gap-1">
          {messages.map((_, i) => (
            <div
              key={i}
              className={`h-0.5 rounded-full transition-all duration-300 ${
                i === currentIdx % messages.length
                  ? "w-4 bg-green-400"
                  : "w-1 bg-gray-700"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Scrolling log */}
      <div
        className="flex-1 overflow-y-auto px-4 py-1.5 font-mono text-[10.5px] leading-relaxed space-y-0.5"
        style={{ scrollbarWidth: "none" }}
      >
        {log.map((m, i) => (
          <div
            key={i}
            className="flex gap-2 opacity-30"
            style={{ opacity: 0.15 + (i / log.length) * 0.22 }}
          >
            <span className={`shrink-0 ${m.speakerColor} opacity-70`}>[{m.tag}]</span>
            <span className={`${m.textColor} truncate`}>{m.text}</span>
          </div>
        ))}

        {/* Currently typing */}
        {currentText && (
          <div className="flex gap-2">
            <span className={`shrink-0 font-semibold ${current.speakerColor}`}>[{current.tag}]</span>
            <span className={`${current.textColor} whitespace-pre-wrap break-words`}>
              {currentText}
              <span className="animate-pulse text-green-400 ml-0.5">▋</span>
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Scanline overlay */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.06) 2px,rgba(0,0,0,0.06) 4px)",
        }}
      />
    </div>
  );
}
