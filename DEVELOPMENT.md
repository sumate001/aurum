# AURUM — Development & Deployment Guide

> Last updated: 2026-06-17

---

## สถานะปัจจุบัน

| Component | สถานะ | หมายเหตุ |
|---|---|---|
| ff-scraper | ✅ ทำงาน | Forex Factory calendar |
| collector | ✅ ทำงาน | รัน cycle ทุก 15 นาที |
| mirofish | ✅ ทำงาน | qwen3.6:35b, ~1.5 นาที/cycle |
| signal engine | ✅ ทำงาน | Entry quality check 4/6 |
| gateway | ✅ ทำงาน | REST API + trend history |
| dashboard | ✅ ทำงาน | http://100.94.37.18:13009 |
| postgres | ✅ ทำงาน | port 13005 |
| redis | ✅ ทำงาน | port 13006 |
| qdrant | ✅ ทำงาน | ยังไม่ได้ใช้งานจริง |
| **Telegram bot** | ⏳ รอ token | ต้องใส่ใน .env |
| **MT5 bridge** | ⏳ รอ Windows | ต้องรันแยกบน Windows |

---

## Deploy ครั้งแรก

### 1. Prerequisites

```bash
# Server ต้องมี
docker compose version   # v2.x+
git

# Ollama ต้องรันอยู่ที่ 100.94.37.18:11434
# และต้อง pull model ก่อน
ollama pull qwen3.6:35b
```

### 2. Clone และตั้งค่า

```bash
git clone <repo>
cd aurum
cp .env.example .env
```

แก้ `.env` ค่าที่ต้องเปลี่ยน:

```env
POSTGRES_PASSWORD=ใส่รหัสที่แข็งแรง

# Telegram (ถ้าพร้อม)
TELEGRAM_BOT_TOKEN=token_จาก_BotFather
TELEGRAM_CHAT_ID=chat_id_ของคุณ

# MT5 (ถ้าพร้อม)
MT5_BRIDGE_URL=http://IP_ของ_Windows:8400
MT5_BRIDGE_API_KEY=ใส่ key ที่ตรงกับ bridge.py
```

### 3. สร้าง data directories และ start

```bash
mkdir -p data/postgres data/qdrant data/redis
docker compose up -d --build
```

### 4. ตรวจสอบว่าขึ้นครบ

```bash
# ดู status ทุก service
docker compose ps

# ทดสอบ health
curl http://localhost:13000/health   # ff-scraper
curl http://localhost:13007/health   # signal engine
curl http://localhost:13008/health   # gateway

# เปิด dashboard
open http://localhost:13009
```

### 5. Trigger cycle แรกทันที (ไม่ต้องรอ 15 นาที)

```bash
docker exec aurum-collector python3 -c "from app.main import run_cycle; run_cycle()"
```

---

## Config สำคัญ (.env)

```env
# Model — ตอนนี้ใช้ model เดียวกันทั้งคู่ (โหลดครั้งเดียว ไม่ swap VRAM)
OLLAMA_MODEL_AGENT=qwen3.6:35b
OLLAMA_MODEL_ORCHESTRATOR=qwen3.6:35b

# Signal logic
SIGNAL_CONFIDENCE_THRESHOLD=60      # macro confidence ขั้นต่ำ
SIGNAL_ENTRY_QUALITY_MIN=4          # entry quality score ขั้นต่ำ (0-6)
SIGNAL_MAX_DAILY=3                  # signal สูงสุดต่อวัน
SIGNAL_RECONFIRM_HOURS=4            # reconfirm ซ้ำทุก 4 ชั่วโมง
SIGNAL_CONF_SURGE=15                # ส่งใหม่ถ้า confidence เพิ่ม >= 15%

# MiroFish
MIROFISH_SIMULATION_ROUNDS=3        # รอบ simulation (เพิ่มได้ถ้าต้องการ quality)
```

---

## Flow การทำงาน

```
ทุก 15 นาที (collector)
  │
  ├─ ดึงราคา GC=F (yfinance) → M15 / H1 / H4
  ├─ ดึง calendar (FF scraper)
  ├─ สร้าง seed document
  │
  └─► MiroFish (qwen3.6:35b)
        ├─ Call 1: จำลอง 6 personas → votes[]
        └─ Call 2: สรุป votes → BULLISH/BEARISH/NEUTRAL + confidence%
              │
              └─► Signal Engine
                    ├─ รัน 7 technical agents บน H1
                    ├─ Entry Quality Check (H4 + H1 + M15) → score 0-6
                    └─ ต้องผ่าน: confidence ≥60% AND quality ≥4/6
                          │
                          └─► Collector ตัดสินใจส่งไหม
                                ├─ อยู่ใน London (07-12 UTC) หรือ NY (13-18 UTC)?
                                ├─ ยังไม่เกิน 3 signals/วัน?
                                └─ มีอะไรเปลี่ยนแปลงจริง?
                                      │
                                      └─► Gateway → PostgreSQL + Telegram
```

---

## Session Trading Windows

| Session | UTC | Bangkok |
|---|---|---|
| London | 07:00 – 12:00 | 14:00 – 19:00 |
| NY | 13:00 – 18:00 | 20:00 – 01:00 |
| Off-hours | นอกนั้น | วิเคราะห์แต่ไม่ส่ง signal |

---

## ล้างข้อมูลและเริ่มใหม่

```bash
# ล้าง DB
docker exec aurum-postgres psql -U aurum -d aurum -c "
TRUNCATE TABLE agent_logs, executions, simulation_reports,
               seed_documents, calendar_events, signals
RESTART IDENTITY CASCADE;"

# ล้าง Redis
docker exec aurum-redis redis-cli KEYS "aurum:*" | xargs docker exec -i aurum-redis redis-cli DEL

# Restart collector
docker compose restart aurum-collector
```

---

## Ops ประจำวัน

```bash
# ดู logs realtime
docker compose logs -f aurum-collector
docker compose logs -f aurum-gateway

# ดูสถานะ trend ปัจจุบัน
curl -s http://localhost:13008/status | python3 -m json.tool

# ดู signal ล่าสุด
curl -s http://localhost:13008/signals?limit=5 | python3 -m json.tool

# ดู history การวิเคราะห์
curl -s http://localhost:13008/trend-history?limit=10 | python3 -m json.tool

# Force รัน cycle ทันที
docker exec aurum-collector python3 -c "from app.main import run_cycle; run_cycle()"
```

---

## Setup Telegram Bot

1. คุยกับ [@BotFather](https://t.me/BotFather) บน Telegram → `/newbot`
2. Copy token ใส่ `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
   ```
3. หา Chat ID:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   # ส่งข้อความหา bot ก่อน แล้วค่อยดู chat.id ใน response
   ```
4. ใส่ใน `.env`:
   ```env
   TELEGRAM_CHAT_ID=123456789
   ```
5. Restart gateway:
   ```bash
   docker compose restart aurum-gateway
   ```

Signal จะส่งมาใน format:
```
🟢 AURUM SIGNAL
Action  : BUY
Entry   : 4,352.00
SL      : 4,338.00
TP1     : 4,366.00
TP2     : 4,384.00
Setup   : EMA Pullback + M15 Confirm
Quality : HIGH (5/6)
Session : LONDON
```

---

## Setup MT5 Bridge (Windows)

```bash
# บน Windows machine ที่รัน MT5
cd services/mt5-bridge
pip install -r requirements.txt

# แก้ใน bridge.py
API_KEY = "ค่าเดียวกับใน .env MT5_BRIDGE_API_KEY"

python bridge.py   # รันค้างไว้
```

ใส่ IP ของ Windows ใน `.env`:
```env
MT5_BRIDGE_URL=http://192.168.1.x:8400
```

---

## พัฒนาต่อ — Priority

### 1. เพิ่มความแม่นยำ Signal (สูง)

**ปัญหา**: บางครั้ง H4 ไม่ align กับ macro ทำให้ HOLD บ่อย

วิธีแก้:
- ลด H4 alignment weight จาก +2 เป็น +1 (ใน `services/signal/app/entry_quality.py`)
- เพิ่ม Support/Resistance levels จาก H4 เป็น key level แทน EMA อย่างเดียว

### 2. Backtesting (สูง)

ตอนนี้ระบบไม่มี backtest — ไม่รู้ว่า entry quality logic มัน work จริงไหม

สิ่งที่ต้องทำ:
```
services/backtest/
  └─ app/
      ├─ runner.py     — วิ่ง entry_quality ย้อนหลังบน historical OHLCV
      └─ report.py     — คำนวณ win rate, avg R:R, max drawdown
```

### 3. Dashboard — Signal Detail Page (กลาง)

ตอนนี้คลิกการ์ด signal แล้วเห็นแค่ราคาใน sidebar

ควรเพิ่ม:
- หน้า `/signals/[id]` แสดง agent votes ทุกตัว
- เหตุผลแบบละเอียดจาก orchestrator
- Chart zoom เฉพาะช่วงนั้น

### 4. Position Tracking (กลาง)

ตอนนี้ `executions` table มีอยู่ใน schema แต่ยังไม่ได้ใช้

ควรเพิ่ม:
- หลัง approve signal → บันทึก lot size และ entry จริง
- Track ว่า TP1/TP2/SL โดน manual หรือ auto
- P&L summary รายวัน/รายสัปดาห์

### 5. News Quality Filter (ต่ำ)

Seed document ตอนนี้ใช้แค่ RSS สั้นๆ

ควรเพิ่ม:
- ดึง full article content
- ให้ LLM summarize เฉพาะประเด็นที่กระทบ Gold
- Weight ข่าวตาม recency และ source reliability

---

## สถาปัตยกรรม Port Reference

| Service | Port | URL |
|---|---|---|
| Dashboard | 13009 | http://server:13009 |
| Gateway API | 13008 | http://server:13008/docs |
| Signal Engine | 13007 | http://server:13007/docs |
| FF Scraper | 13000 | http://server:13000/health |
| MiroFish | 13001 | http://server:13001/docs |
| Qdrant | 13003 | http://server:13003/dashboard |
| PostgreSQL | 13005 | — |
| Redis | 13006 | — |
| Ollama | 11434 | http://100.94.37.18:11434 (shared) |

---

## Rebuild หลังแก้ code

```bash
# แก้ signal engine
docker compose build aurum-signal && docker compose up -d aurum-signal

# แก้ collector logic
docker compose build aurum-collector && docker compose up -d aurum-collector

# แก้ dashboard UI
docker compose build aurum-dashboard && docker compose up -d aurum-dashboard

# แก้ mirofish / model config
docker compose up -d aurum-mirofish   # ไม่ต้อง build ถ้าแค่เปลี่ยน .env

# Build ทั้งหมด
docker compose up -d --build
```
