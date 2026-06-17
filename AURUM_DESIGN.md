# AURUM — System Design Document v1.1
> Gold Intelligence & Multi-Agent Trading Signal System

---

## 1. Project Overview

| Item | Value |
|---|---|
| Project name | AURUM |
| Server | 100.94.37.18 (NVIDIA A5000 × 2, 32GB VRAM total) |
| Deploy method | Docker Compose (isolated stack) |
| Primary asset | GOLD# (XM Global MT5) |
| Alert channel | Telegram Bot |
| Simulation cadence | Every 15–60 min (configurable per session) |
| Execution mode | Alert + Semi-auto (human approval gate) |

---

## 2. Architecture — 4 Layers

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 · Data Collection                              │
│  Macro news · Bank reports · Price · Sentiment          │
│  Forex Factory calendar (High impact, USD/XAU only)     │
└────────────────────────┬────────────────────────────────┘
                         │ seed_document.md
┌────────────────────────▼────────────────────────────────┐
│  LAYER 2 · MiroFish Simulation                          │
│  Swarm agents · Mem0 · Ollama (shared) · Market personas│
└────────────────────────┬────────────────────────────────┘
                         │ macro_signal (direction + TF + confidence)
┌────────────────────────▼────────────────────────────────┐
│  LAYER 3 · Technical Signal Engine                      │
│  Indicator agents · Orchestrator LLM · Fusion           │
└────────────────────────┬────────────────────────────────┘
                         │ final_signal (BUY/SELL/HOLD + entry/SL/TP)
┌────────────────────────▼────────────────────────────────┐
│  LAYER 4 · Execution & Alert                            │
│  Telegram alert · Approval gate · MT5 EA                │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Docker Services

| Service | Image | Port | Role |
|---|---|---|---|
| `aurum-ff-scraper` | custom build (ForexFactoryScrapper) | 13000 | Forex Factory calendar scraper API |
| `aurum-mirofish` | custom build | 13001 | Swarm simulation engine |
| `aurum-mem0` | mem0ai/mem0 | 13002 | Agent memory layer |
| `aurum-qdrant` | qdrant/qdrant | 13003/13004 | Vector store for Mem0 |
| `aurum-postgres` | postgres:16 | 13005 | Persistent storage (signals, logs) |
| `aurum-redis` | redis:7-alpine | 13006 | Job queue + cache (FF cache ด้วย) |
| `aurum-collector` | custom build | — | Data collection scheduler |
| `aurum-signal` | custom build | 13007 | Technical signal engine API |
| `aurum-gateway` | custom build | 13008 | Main API + Telegram webhook |
| `aurum-dashboard` | custom build | 13009 | Web UI (signal monitor) |

**Docker network**: `aurum_net` (isolated bridge)
**Volume prefix**: `aurum_*` (no shared volumes with other projects)

### Ollama — shared instance (ไม่ deploy ใหม่)
- **ใช้ Ollama เดิม** ที่รันอยู่บน host port `11434`
- AURUM เข้าถึงผ่าน `http://100.94.37.18:11434` (host network)
- ไม่กระทบ service อื่นที่ใช้ Ollama อยู่แล้ว
- Ollama จัดการ queue และ VRAM sharing ให้อัตโนมัติ

---

## 4. LLM Model Plan

| Task | Model | VRAM est. |
|---|---|---|
| MiroFish simulation (agents) | qwen3:8b | ~6GB |
| Orchestrator / signal fusion | qwen3:14b | ~10GB |
| Seed document summarization | qwen3:8b | shared |

Total VRAM budget สำหรับ AURUM: ~16GB
ใช้ GPU 1 หลัก, GPU 2 สำรอง — ไม่ชนกับ service อื่นเพราะ Ollama จัดการ queue เอง

---

## 5. Data Collection Sources

### 5.1 Macro News
- **Reuters RSS** — `feeds.reuters.com/reuters/businessNews`
- **FX Street RSS** — `fxstreet.com/rss/news`
- **Investing.com Economic Calendar** — scrape หน้า economic calendar
- **Fed / FOMC** — federalreserve.gov press releases RSS

### 5.2 Bank Research
- **Goldman Sachs** — public research summaries (scrape)
- **JPMorgan** — market commentary (scrape)
- **World Gold Council** — gold.org/goldhub/research

### 5.3 Price Data
- **yfinance** — OHLCV backup (GC=F futures)
- **MT5 Python API** — real price feed จาก XM account (primary)
- Symbol: `GOLD#`, configurable per run

### 5.4 Sentiment
- **Telegram channels** — gold/forex channels (read-only)
- **Reddit** — r/Forex, r/Gold via PRAW

### 5.5 Forex Factory Calendar ✨ (เพิ่มใหม่)
- **Source**: ForexFactoryScrapper (self-hosted container `aurum-ff-scraper`)
- **Filter**: Currency = USD, XAU — Impact = High เท่านั้น
- **Schedule**: scrape ทุก 1 ชั่วโมง (ป้องกัน IP block)
- **Cache**: Redis TTL 55 นาที (ไม่ hit FF ซ้ำภายใน window เดียว)
- **Fallback**: Investing.com calendar ถ้า FF scraper พัง
- **Output fields**: datetime, currency, impact, event_name, actual, forecast, previous
- **ใช้งาน**: แจ้งเตือน high-impact event ที่กำลังจะมาถึง + inject เข้า seed document
- **ข้อควรระวัง**: FF ไม่มี official API, ToS ห้าม scrape — ใช้ rate limit เข้มงวด

#### ตัวอย่าง event ที่ filter ผ่าน (High impact, USD/XAU)
```
2026-06-15 21:30 | USD | 🔴 High | Core CPI m/m       | Actual: 0.3% | Forecast: 0.2%
2026-06-15 23:00 | USD | 🔴 High | Fed Chair Speech    | Actual: —    | Forecast: —
2026-06-18 03:00 | USD | 🔴 High | FOMC Meeting Minutes| Actual: —    | Forecast: —
```

#### Logic การใช้ใน seed document
```
IF upcoming_high_impact_event within 2 hours:
    → เพิ่ม warning ใน seed: "⚠️ High-impact event in X min: [event_name]"
    → MiroFish จะ simulate ว่า agents react อย่างไรก่อน/หลัง event
IF actual vs forecast surprise > threshold:
    → trigger immediate re-simulation
```

---

## 6. MiroFish Agent Personas

| Persona | Behavior |
|---|---|
| Central bank buyer | Accumulates on dips, long-term bullish bias |
| Hedge fund manager | Follows momentum, cuts quickly on reversal |
| Retail trader (long) | FOMO buyer, weak hands |
| Retail trader (short) | Counter-trend, stops tight |
| Market maker | Liquidity provider, fade extremes |
| Macro analyst | Driven by DXY, yields, inflation data |

Simulation output:
- **Direction**: BULLISH / BEARISH / NEUTRAL
- **Confidence**: 0–100%
- **Recommended timeframe**: M15 / H1 / H4 / D1
- **Key reasoning**: 2–3 sentence summary

---

## 7. Technical Signal Agents (Layer 3)

| Agent | Indicator | Signal type |
|---|---|---|
| `agent_trend` | EMA 20/50/200 | Trend direction |
| `agent_momentum` | RSI 14 | Overbought/oversold |
| `agent_volatility` | ATR 14 | Stop distance sizing |
| `agent_breakout` | Donchian Channel | Breakout confirmation |
| `agent_structure` | Support/Resistance | Key levels |
| `agent_smc` | SMC (OB, FVG, BOS) | Smart money bias |
| `agent_volume` | Volume + VWAP | Conviction filter |

**Orchestrator**: qwen3:14b
- รับ output จากทุก agent + macro_signal จาก MiroFish
- resolve conflicts ระหว่าง technical และ macro
- output final_signal

---

## 8. Final Signal Schema

```json
{
  "signal_id": "uuid",
  "timestamp": "2026-06-15T10:30:00Z",
  "symbol": "GOLD#",
  "broker": "XM",
  "action": "BUY | SELL | HOLD",
  "timeframe": "H1",
  "entry": 3285.50,
  "sl": 3272.00,
  "tp1": 3300.00,
  "tp2": 3315.00,
  "confidence": 78,
  "macro_bias": "BULLISH",
  "macro_confidence": 82,
  "technical_consensus": "6/7 agents agree",
  "upcoming_events": [
    {
      "event": "Fed Chair Speech",
      "in_minutes": 45,
      "impact": "High"
    }
  ],
  "reasoning": "Fed dovish tone + EMA bullish stack + SMC demand zone",
  "status": "PENDING_APPROVAL"
}
```

---

## 9. Telegram Alert Format

```
🟢 AURUM SIGNAL #042
━━━━━━━━━━━━━━━━━━━━
Pair    : GOLD# (XM)
Action  : BUY
TF      : H1
━━━━━━━━━━━━━━━━━━━━
Entry   : 3,285.50
SL      : 3,272.00 (-135 pips)
TP1     : 3,300.00 (+145 pips)
TP2     : 3,315.00 (+295 pips)
━━━━━━━━━━━━━━━━━━━━
Confidence  : 78%
Macro bias  : 🟢 BULLISH (82%)
Tech agents : 6/7 agree
━━━━━━━━━━━━━━━━━━━━
⚠️ Fed Chair Speech in 45 min
━━━━━━━━━━━━━━━━━━━━
📋 Fed dovish tone + EMA bullish
   stack + SMC demand zone active

[✅ APPROVE] [❌ REJECT] [⚙️ ADJUST]
```

---

## 10. Approval Gate Flow

```
Signal generated
      ↓
Telegram alert sent (inline keyboard)
      ↓
User taps [APPROVE] → EA executes on MT5
User taps [REJECT]  → Signal discarded, logged
User taps [ADJUST]  → Bot asks: lot size? → confirm → execute
      ↓
Execution result sent back to Telegram
Position monitored → TP/SL hit → notification
```

---

## 11. MT5 Integration

- **Method**: MT5 Python API (`MetaTrader5` package) บน Windows workstation
- **Bridge service**: `aurum-mt5-bridge` (Python script รันบน Windows)
  - รับ signal จาก `aurum-gateway` ผ่าน REST API
  - execute order บน MT5
  - report back status
- **Symbol**: `GOLD#`
- **Filling**: `ORDER_FILLING_IOC` (XM standard)
- **Contract size**: 100

---

## 12. Scheduler (Simulation Cadence)

| Session | Time (UTC+7) | Interval |
|---|---|---|
| Asian open | 07:00–09:00 | every 60 min |
| London open | 14:00–17:00 | every 15 min |
| NY open | 19:00–22:00 | every 15 min |
| Off-hours | 09:00–14:00 | every 60 min |

Manual trigger: `/simulate` command ผ่าน Telegram bot

**Forex Factory event trigger** (เพิ่มใหม่):
- ถ้ามี High-impact event ใน 2 ชั่วโมงข้างหน้า → force simulate ทันที
- หลัง actual release ออกมา → re-simulate ภายใน 5 นาที

---

## 13. Database Schema (PostgreSQL)

Tables:
- `signals` — signal history ทั้งหมด
- `executions` — order ที่ execute แล้ว + result
- `seed_documents` — seed doc แต่ละ cycle
- `simulation_reports` — MiroFish output
- `agent_logs` — technical agent outputs per cycle
- `calendar_events` — Forex Factory events ที่ดึงมา + actual values

---

## 14. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinate signal | Human approval gate บังคับทุก signal |
| MiroFish simulation ผิด | Confidence threshold < 60% → HOLD อัตโนมัติ |
| News source down | Fallback sources + graceful degrade |
| MT5 bridge disconnect | Signal queue ใน Redis, retry 3 ครั้ง |
| VRAM contention กับ service อื่น | Ollama จัดการ queue อัตโนมัติ, model unload policy |
| False signal flood | Rate limit: max 3 signals ต่อชั่วโมง |
| FF scraper โดน block | Rate limit 1 req/ชั่วโมง + Redis cache 55 นาที + Investing.com fallback |
| FF เปลี่ยน HTML structure | Health check container แจ้งเตือน Telegram ถ้า scraper พัง |
| Trade เปิดตอน High-impact event | ⚠️ Warning ใน signal + user approve เอง |

---

## 15. Project Structure

```
aurum/
├── docker-compose.yml
├── .env.example
├── .env                         ← ไม่ commit
├── AURUM_DESIGN.md
├── services/
│   ├── ff-scraper/              ← Forex Factory scraper (ForexFactoryScrapper fork)
│   │   ├── Dockerfile
│   │   └── config.py
│   ├── collector/               ← Layer 1
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── sources/
│   │       ├── news.py
│   │       ├── banks.py
│   │       ├── price.py
│   │       ├── sentiment.py
│   │       └── calendar.py      ← FF calendar client
│   ├── mirofish/                ← Layer 2 (fork + patch)
│   │   ├── Dockerfile
│   │   └── patches/
│   ├── signal/                  ← Layer 3
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── agents/
│   ├── gateway/                 ← Layer 4 API + Telegram
│   │   ├── Dockerfile
│   │   └── main.py
│   ├── dashboard/               ← Web UI
│   │   ├── Dockerfile
│   │   └── app/
│   └── mt5-bridge/              ← Windows side
│       └── bridge.py
├── shared/
│   ├── schemas/                 ← Pydantic models
│   └── utils/
└── data/
    ├── postgres/
    ├── qdrant/
    └── redis/
```

---

## ⚠️ Pre-build Checklist

- [ ] Telegram Bot token สร้างแล้ว (@BotFather)
- [ ] Telegram Chat ID ของคุณ
- [ ] XM MT5 account credential (สำหรับ Python API)
- [ ] ยืนยัน port 13000–13009 ว่างบน server
- [ ] Docker + Docker Compose installed บน server
- [ ] NVIDIA Container Toolkit installed (สำหรับ GPU passthrough)
- [ ] Ollama บน host port 11434 รันอยู่และ pull qwen3:8b + qwen3:14b แล้ว

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| v1.0 | 2026-06-15 | Initial design |
| v1.1 | 2026-06-15 | เพิ่ม Forex Factory calendar (Section 5.5), แก้ Ollama เป็น shared instance, เพิ่ม calendar_events table, เพิ่ม FF-related risks, ปรับ signal schema + Telegram format |

