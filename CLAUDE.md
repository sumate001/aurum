# AURUM — Claude Code Project Context
> Version: 1.1 | Last updated: 2026-06-15
> Gold Intelligence & Multi-Agent Trading Signal System

---

## 🎯 Project Purpose

AURUM เป็นระบบ AI-powered trading signal สำหรับ GOLD# บน XM Global MT5
ทำงาน 4 layer: Data Collection → MiroFish Simulation → Technical Signal Engine → Execution

**ไม่ใช่ fully automated trading bot** — ทุก signal ต้องผ่าน human approval ก่อน execute

---

## 🖥️ Infrastructure

```
Server        : 100.94.37.18 (Ubuntu Linux)
GPU           : NVIDIA A5000 × 2 (32GB VRAM รวม)
Ollama        : http://100.94.37.18:11434 (shared, ไม่ deploy ใหม่)
Deploy        : Docker Compose (isolated stack)
Network       : aurum_net (bridge, isolated)
Volume prefix : aurum_*
Port range    : 13000–13009
```

### Models (pull ก่อน start)
```bash
ollama pull qwen3:8b     # MiroFish agents + seed summarization
ollama pull qwen3:14b    # Orchestrator / signal fusion
```

---

## 📁 Project Structure

```
aurum/
├── CLAUDE.md                    ← this file
├── AURUM_DESIGN.md              ← full design document
├── docker-compose.yml           ← main compose file
├── .env.example                 ← template (commit this)
├── .env                         ← secrets (never commit)
│
├── services/
│   ├── ff-scraper/              ← Forex Factory calendar scraper
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py          ← Flask app (ForexFactoryScrapper fork)
│   │       ├── scraper.py       ← FF scraping logic
│   │       └── cache.py         ← Redis cache layer
│   │
│   ├── collector/               ← Layer 1: Data collection scheduler
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py          ← APScheduler entrypoint
│   │       ├── seed_builder.py  ← รวม sources → seed_document.md
│   │       └── sources/
│   │           ├── news.py      ← Reuters/FXStreet RSS
│   │           ├── banks.py     ← Goldman/JPMorgan scrape
│   │           ├── price.py     ← yfinance + MT5 API
│   │           ├── sentiment.py ← Reddit PRAW
│   │           └── calendar.py  ← FF scraper client + Investing.com fallback
│   │
│   ├── mirofish/                ← Layer 2: Swarm simulation
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py          ← FastAPI entrypoint
│   │       ├── simulation.py    ← MiroFish core (fork from 666ghj/MiroFish)
│   │       ├── personas.py      ← Agent persona definitions
│   │       ├── memory.py        ← Mem0 integration (replaces Zep)
│   │       └── report.py        ← Parse simulation → macro_signal JSON
│   │
│   ├── signal/                  ← Layer 3: Technical signal engine
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py          ← FastAPI entrypoint
│   │       ├── orchestrator.py  ← qwen3:14b fusion logic
│   │       ├── fusion.py        ← macro + technical → final_signal
│   │       └── agents/
│   │           ├── base.py      ← BaseIndicatorAgent class
│   │           ├── trend.py     ← EMA 20/50/200
│   │           ├── momentum.py  ← RSI 14
│   │           ├── volatility.py ← ATR 14
│   │           ├── breakout.py  ← Donchian Channel
│   │           ├── structure.py ← Support/Resistance
│   │           ├── smc.py       ← SMC (OB, FVG, BOS)
│   │           └── volume.py    ← Volume + VWAP
│   │
│   ├── gateway/                 ← Layer 4: API + Telegram bot
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py          ← FastAPI entrypoint
│   │       ├── telegram.py      ← python-telegram-bot handler
│   │       ├── approval.py      ← Approval gate logic
│   │       └── mt5_client.py    ← HTTP client → mt5-bridge
│   │
│   ├── dashboard/               ← Web UI (Next.js)
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── src/
│   │       ├── app/
│   │       │   ├── page.tsx     ← Signal monitor (main)
│   │       │   ├── history/     ← Signal history
│   │       │   └── calendar/    ← FF economic calendar view
│   │       └── components/
│   │           ├── SignalCard.tsx
│   │           ├── MacroBias.tsx
│   │           ├── AgentGrid.tsx
│   │           ├── CalendarEvents.tsx
│   │           └── PriceChart.tsx
│   │
│   └── mt5-bridge/              ← Windows side (ไม่ใน Docker)
│       ├── bridge.py            ← FastAPI รันบน Windows
│       ├── requirements.txt
│       └── README.md            ← วิธี setup บน Windows
│
├── shared/
│   ├── schemas/
│   │   ├── signal.py            ← SignalSchema Pydantic model
│   │   ├── macro.py             ← MacroSignalSchema
│   │   └── calendar.py          ← CalendarEventSchema
│   └── utils/
│       ├── logger.py            ← Structured logging
│       └── redis_client.py      ← Shared Redis helper
│
└── data/                        ← Docker volumes mount here
    ├── postgres/
    ├── qdrant/
    └── redis/
```

---

## 🐳 Docker Services

| Service | Image | Port | Notes |
|---|---|---|---|
| `aurum-ff-scraper` | custom | 13000 | Forex Factory calendar API |
| `aurum-mirofish` | custom | 13001 | Simulation engine |
| `aurum-mem0` | mem0ai/mem0 | 13002 | Agent memory |
| `aurum-qdrant` | qdrant/qdrant | 13003 (HTTP) / 13004 (gRPC) | Vector store |
| `aurum-postgres` | postgres:16 | 13005 | Main DB |
| `aurum-redis` | redis:7-alpine | 13006 | Queue + cache |
| `aurum-collector` | custom | — | No exposed port, internal only |
| `aurum-signal` | custom | 13007 | Signal engine API |
| `aurum-gateway` | custom | 13008 | Main API + Telegram webhook |
| `aurum-dashboard` | custom | 13009 | Web UI |

**Ollama**: ใช้ host instance `http://100.94.37.18:11434` — ไม่มีใน compose

---

## ⚙️ Environment Variables (.env)

```env
# ─── Ollama ───────────────────────────────────────────
OLLAMA_BASE_URL=http://100.94.37.18:11434
OLLAMA_MODEL_AGENT=qwen3:8b
OLLAMA_MODEL_ORCHESTRATOR=qwen3:14b

# ─── Telegram ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# ─── PostgreSQL ───────────────────────────────────────
POSTGRES_DB=aurum
POSTGRES_USER=aurum
POSTGRES_PASSWORD=change_this_password
POSTGRES_HOST=aurum-postgres
POSTGRES_PORT=5432

# ─── Redis ────────────────────────────────────────────
REDIS_HOST=aurum-redis
REDIS_PORT=6379

# ─── Qdrant ───────────────────────────────────────────
QDRANT_HOST=aurum-qdrant
QDRANT_PORT=6333

# ─── MT5 Bridge (Windows) ─────────────────────────────
MT5_BRIDGE_URL=http://WINDOWS_IP:8400
MT5_BRIDGE_API_KEY=change_this_key
MT5_SYMBOL=GOLD#
MT5_FILLING=ORDER_FILLING_IOC
MT5_CONTRACT_SIZE=100

# ─── Signal Config ────────────────────────────────────
SIGNAL_CONFIDENCE_THRESHOLD=60
SIGNAL_MAX_PER_HOUR=3
SIMULATION_INTERVAL_MINUTES=30

# ─── Forex Factory ────────────────────────────────────
FF_SCRAPE_INTERVAL_MINUTES=60
FF_CACHE_TTL_SECONDS=3300
FF_FILTER_CURRENCIES=USD,XAU
FF_FILTER_IMPACT=high
FF_PRE_EVENT_WARN_MINUTES=120

# ─── MiroFish ─────────────────────────────────────────
MIROFISH_SIMULATION_ROUNDS=30
MIROFISH_MIN_CONFIDENCE=60
```

---

## 🗄️ Database Schema (PostgreSQL)

```sql
-- signals: signal ทั้งหมดที่ generate
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    broker VARCHAR(20) DEFAULT 'XM',
    action VARCHAR(10) NOT NULL,        -- BUY | SELL | HOLD
    timeframe VARCHAR(10),
    entry DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp1 DECIMAL(10,2),
    tp2 DECIMAL(10,2),
    confidence INTEGER,
    macro_bias VARCHAR(10),
    macro_confidence INTEGER,
    technical_consensus VARCHAR(50),
    reasoning TEXT,
    upcoming_events JSONB,
    status VARCHAR(20) DEFAULT 'PENDING_APPROVAL',  -- PENDING|APPROVED|REJECTED|EXECUTED|CANCELLED
    raw_macro JSONB,
    raw_technical JSONB
);

-- executions: order ที่ execute แล้วบน MT5
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id),
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    mt5_ticket BIGINT,
    lot_size DECIMAL(5,2),
    actual_entry DECIMAL(10,2),
    actual_sl DECIMAL(10,2),
    actual_tp DECIMAL(10,2),
    status VARCHAR(20),         -- OPEN | CLOSED_TP | CLOSED_SL | CLOSED_MANUAL
    pnl DECIMAL(10,2),
    close_price DECIMAL(10,2),
    closed_at TIMESTAMPTZ
);

-- seed_documents: seed doc แต่ละ cycle
CREATE TABLE seed_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(20),
    content TEXT,
    sources JSONB,              -- list of sources used
    word_count INTEGER
);

-- simulation_reports: MiroFish output ดิบ
CREATE TABLE simulation_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seed_id UUID REFERENCES seed_documents(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    direction VARCHAR(10),
    confidence INTEGER,
    recommended_tf VARCHAR(10),
    reasoning TEXT,
    raw_output JSONB
);

-- agent_logs: technical agent output ต่อ cycle
CREATE TABLE agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    agent_name VARCHAR(50),
    signal VARCHAR(10),
    value DECIMAL(10,4),
    metadata JSONB
);

-- calendar_events: Forex Factory events
CREATE TABLE calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    event_datetime TIMESTAMPTZ,
    currency VARCHAR(10),
    impact VARCHAR(10),
    event_name VARCHAR(200),
    actual VARCHAR(50),
    forecast VARCHAR(50),
    previous VARCHAR(50),
    surprise_pct DECIMAL(5,2)   -- (actual - forecast) / |forecast| * 100
);
```

---

## 📡 Internal API Contracts

### collector → mirofish
```
POST http://aurum-mirofish:8000/simulate
Body: {
  "seed_document": "string (markdown)",
  "symbol": "GOLD#",
  "upcoming_events": [...],
  "simulation_rounds": 30
}
Response: {
  "direction": "BULLISH|BEARISH|NEUTRAL",
  "confidence": 0-100,
  "recommended_tf": "M15|H1|H4|D1",
  "reasoning": "string",
  "raw_output": {...}
}
```

### collector → signal
```
POST http://aurum-signal:8000/analyze
Body: {
  "symbol": "GOLD#",
  "macro_signal": { ...macro output... },
  "ohlcv": { "M15": [...], "H1": [...], "H4": [...] }
}
Response: {
  "action": "BUY|SELL|HOLD",
  "timeframe": "H1",
  "entry": 3285.50,
  "sl": 3272.00,
  "tp1": 3300.00,
  "tp2": 3315.00,
  "confidence": 78,
  "technical_consensus": "6/7 agents agree",
  "agent_outputs": [...],
  "reasoning": "string"
}
```

### gateway → mt5-bridge
```
POST http://MT5_BRIDGE_URL/order
Headers: { "X-API-Key": MT5_BRIDGE_API_KEY }
Body: {
  "symbol": "GOLD#",
  "action": "BUY",
  "lot_size": 0.1,
  "entry": 3285.50,
  "sl": 3272.00,
  "tp": 3300.00,
  "comment": "AURUM#042"
}
Response: {
  "ticket": 123456789,
  "status": "EXECUTED",
  "actual_entry": 3285.60
}
```

---

## 🤖 MiroFish Agent Personas

```python
PERSONAS = [
    {
        "name": "Central Bank Buyer",
        "personality": "Conservative institutional buyer. Accumulates gold on dips. Long-term bullish bias. Reacts strongly to inflation data and geopolitical risk.",
        "memory": "long_term"
    },
    {
        "name": "Hedge Fund Manager",
        "personality": "Momentum follower. Cuts positions quickly on reversal signals. Watches DXY and yields closely.",
        "memory": "short_term"
    },
    {
        "name": "Retail Trader Long",
        "personality": "FOMO buyer. Enters late in trends. Weak hands, panic sells on volatility.",
        "memory": "short_term"
    },
    {
        "name": "Retail Trader Short",
        "personality": "Counter-trend trader. Fades rallies. Keeps stops tight.",
        "memory": "short_term"
    },
    {
        "name": "Market Maker",
        "personality": "Liquidity provider. Fades extremes. Hunts stop clusters above/below key levels.",
        "memory": "medium_term"
    },
    {
        "name": "Macro Analyst",
        "personality": "Driven by fundamentals. DXY inverse correlation, real yields, inflation expectations. Ignores short-term noise.",
        "memory": "long_term"
    }
]
```

---

## 📊 Technical Agent Base Class

```python
# services/signal/app/agents/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal
import pandas as pd

@dataclass
class AgentSignal:
    agent_name: str
    signal: Literal["BUY", "SELL", "HOLD"]
    value: float
    metadata: dict

class BaseIndicatorAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        """
        ohlcv columns: open, high, low, close, volume
        index: datetime
        """
        pass
```

---

## 📅 Forex Factory Integration

### Flow
```
APScheduler (every 60 min)
    → GET http://aurum-ff-scraper:5000/api/calendar?currencies=USD,XAU&impact=high
    → Check Redis cache (TTL 55 min)
    → If cache miss: scrape FF → cache → return
    → Filter: only USD + XAU, High impact
    → Store to calendar_events table
    → Check upcoming events within 2 hours
    → If found: inject warning into seed document
    → If actual released: compare vs forecast → re-simulate if surprise > 0.1%
```

### FF Scraper endpoints (port 13000)
```
GET /api/calendar?start_date=YYYY-MM-DD&currencies=USD,XAU&impact=high
GET /health
```

---

## ⏰ Scheduler Logic (APScheduler)

```python
# services/collector/app/main.py

SCHEDULE = {
    "asian_open":  {"start": "07:00", "end": "09:00", "interval_min": 60},
    "london_open": {"start": "14:00", "end": "17:00", "interval_min": 15},
    "ny_open":     {"start": "19:00", "end": "22:00", "interval_min": 15},
    "off_hours":   {"default": True,                   "interval_min": 60},
}

# Telegram commands
# /simulate  → force run simulation now
# /status    → show last signal
# /calendar  → show upcoming high-impact events
# /pause     → pause auto simulation
# /resume    → resume auto simulation
```

---

## 📱 Telegram Signal Format

```
🟢 AURUM SIGNAL #042
━━━━━━━━━━━━━━━━━━━━
Pair    : GOLD# (XM)
Action  : BUY
TF      : H1
━━━━━━━━━━━━━━━━━━━━
Entry   : 3,285.50
SL      : 3,272.00  (-135 pips)
TP1     : 3,300.00  (+145 pips)
TP2     : 3,315.00  (+295 pips)
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

## 🔧 Build Order

Build ตาม sequence นี้เสมอ — แต่ละ service depend on ตัวก่อนหน้า:

```
1. docker-compose.yml + .env.example
2. shared/schemas/ + shared/utils/
3. aurum-postgres (init schema)
4. aurum-redis
5. aurum-qdrant
6. aurum-ff-scraper
7. aurum-mem0
8. aurum-collector (sources ทีละ file)
9. aurum-mirofish
10. aurum-signal (agents ทีละ agent)
11. aurum-gateway (Telegram bot)
12. aurum-dashboard (UI)
13. mt5-bridge (Windows, แยก)
```

---

## ⚠️ Critical Rules

1. **ห้าม execute order โดยไม่ผ่าน approval gate** ทุก signal ต้องมี status `PENDING_APPROVAL` ก่อนเสมอ
2. **ห้าม commit .env** ใช้ .env.example เท่านั้น
3. **ห้าม share volumes กับ project อื่น** ใช้ prefix `aurum_` ทุก volume
4. **Confidence < 60% → HOLD อัตโนมัติ** ไม่ส่ง signal ออก
5. **Max 3 signals ต่อชั่วโมง** rate limit ใน gateway
6. **FF scraper: max 1 request ต่อชั่วโมงต่อ endpoint** ป้องกัน IP block
7. **ทุก service ต้องมี /health endpoint** สำหรับ Docker healthcheck
8. **Log ทุก signal และ decision** แม้จะเป็น HOLD หรือ REJECT

---

## 🚀 Quick Start (หลัง clone)

```bash
# 1. copy env
cp .env.example .env
# แก้ .env ใส่ค่าจริง

# 2. สร้าง data directories
mkdir -p data/postgres data/qdrant data/redis

# 3. build และ start ทั้งหมด
docker compose up -d --build

# 4. ดู logs
docker compose logs -f aurum-collector
docker compose logs -f aurum-gateway

# 5. ทดสอบ health
curl http://localhost:13000/health   # ff-scraper
curl http://localhost:13007/health   # signal engine
curl http://localhost:13008/health   # gateway

# 6. trigger simulation แรก
curl -X POST http://localhost:13008/simulate
```

---

## 📝 Notes สำหรับ Claude Code

- เวลาเขียน Dockerfile ให้ใช้ multi-stage build เสมอ (builder + runtime)
- Python services ใช้ `python:3.11-slim` เป็น base
- Next.js dashboard ใช้ `node:20-alpine`
- ทุก Python service ใช้ `uv` เป็น package manager
- Internal communication ผ่าน service name บน `aurum_net` เท่านั้น ห้ามใช้ IP โดยตรง
- ทุก FastAPI service ต้องมี `/health` และ `/docs` (Swagger)
- Error handling: ถ้า source ใด source หนึ่งพัง ให้ log แล้ว continue ไม่ใช่ crash
- ใช้ structured logging (JSON format) ทุก service
