"""
Entry Quality Checker — ประเมินว่า "ตอนนี้" เป็นจังหวะดีที่จะเข้าเทรดไหม

คำถามที่ต้องผ่านทั้งหมดก่อน signal จะออก:
  1. H4 trend ตรงกับ macro bias ไหม? (ทิศทางใหญ่)
  2. H1 ราคา pull back มาอยู่ในโซนดีไหม? (ไม่ overextended)
  3. M15 momentum กลับมาในทิศทางที่ต้องการไหม? (trigger)

Score 0-6  |  ต้องได้ >= 4 ถึงจะ fire signal
"""

import pandas as pd


def _to_df(records: list) -> pd.DataFrame | None:
    if not records:
        return None
    df = pd.DataFrame(records)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    return df if len(df) >= 20 else None


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def check_entry_quality(ohlcv_dict: dict, direction: str) -> dict:
    """
    direction: "BULLISH" | "BEARISH"

    Returns:
      score         int 0-6
      quality       "HIGH" | "MEDIUM" | "LOW"
      setup_type    str  — human-readable description of the setup
      details       list[str]  — for reasoning
      entry_zone    float | None  — key level price is near (EMA20/50)
      h4_aligned    bool
      near_level    bool
      m15_confirmed bool
    """
    score = 0
    details: list[str] = []
    entry_zone: float | None = None

    # ── 1. H4: big-picture trend alignment OR reversal extreme (max +2) ───
    h4_df = _to_df(ohlcv_dict.get("H4", []))
    h4_aligned  = False
    is_reversal = False

    if h4_df is not None:
        close_h4 = h4_df["close"]
        ema20_h4 = float(close_h4.ewm(span=20).mean().iloc[-1])
        ema50_h4 = float(close_h4.ewm(span=50).mean().iloc[-1])
        last_h4  = float(close_h4.iloc[-1])
        rsi_h4   = float(_rsi(close_h4).iloc[-1])

        if direction == "BULLISH":
            h4_aligned  = last_h4 > ema20_h4 and ema20_h4 >= ema50_h4 * 0.9995
            # Reversal: ราคาลงต่ำกว่า EMA20 + RSI oversold → buy the dip
            is_reversal = rsi_h4 < 30 and last_h4 < ema20_h4 * 0.997
        else:
            h4_aligned  = last_h4 < ema20_h4 and ema20_h4 <= ema50_h4 * 1.0005
            # Reversal: ราคาสูงกว่า EMA20 + RSI overbought → sell the spike
            is_reversal = rsi_h4 > 70 and last_h4 > ema20_h4 * 1.003

        if h4_aligned:
            score += 2
            details.append(f"H4 trend {direction.lower()} (EMA stack ยืนยัน)")
        elif is_reversal:
            h4_aligned = True
            score += 2
            label = "overbought" if direction == "BEARISH" else "oversold"
            details.append(f"H4 reversal zone — RSI {rsi_h4:.0f} ({label}), ราคา overextended จาก EMA20")
        else:
            details.append(f"H4 trend ไม่ตรงกับ {direction} — ยังไม่ align (RSI {rsi_h4:.0f})")
    else:
        # ไม่มี H4 data → ใช้ macro confidence เป็น proxy
        score += 1
        details.append("ไม่มีข้อมูล H4 (ใช้ macro bias แทน)")
        h4_aligned = True  # อนุญาตให้ผ่านด้วย macro

    # ── 2. H1: entry zone quality (max +3) ────────────────────────────────
    h1_df = _to_df(ohlcv_dict.get("H1", []))
    near_level = False
    not_overextended = False
    rsi_h1_valid = False

    if h1_df is not None:
        close_h1 = h1_df["close"]
        ema20_h1 = float(close_h1.ewm(span=20).mean().iloc[-1])
        ema50_h1 = float(close_h1.ewm(span=50).mean().iloc[-1])
        last_h1  = float(close_h1.iloc[-1])
        atr_h1   = _atr(h1_df)
        rsi_h1   = float(_rsi(close_h1).iloc[-1])

        dist_ema20 = abs(last_h1 - ema20_h1)
        dist_ema50 = abs(last_h1 - ema50_h1)

        # 2a. ไม่ overextended (+1)
        not_overextended = dist_ema20 <= 2.5 * atr_h1
        if not_overextended:
            score += 1
            details.append(f"H1 ไม่ overextended (ห่าง EMA20 {dist_ema20:.1f} ≤ 2.5×ATR)")
        else:
            details.append(f"H1 overextended — ราคาวิ่งไป {dist_ema20:.1f} จาก EMA20 (ATR={atr_h1:.1f})")

        # 2b. อยู่ใน pullback zone / ใกล้ key level (+1)
        if dist_ema20 <= 1.5 * atr_h1:
            near_level = True
            entry_zone = round(ema20_h1, 2)
            score += 1
            details.append(f"H1 pullback มาถึง EMA20 zone ({ema20_h1:.2f})")
        elif dist_ema50 <= 1.5 * atr_h1:
            near_level = True
            entry_zone = round(ema50_h1, 2)
            score += 1
            details.append(f"H1 ใกล้ EMA50 zone ({ema50_h1:.2f})")
        else:
            details.append(f"H1 ราคายังไม่ pullback ถึง key level (EMA20={ema20_h1:.2f}, EMA50={ema50_h1:.2f})")

        # 2c. RSI ไม่อยู่ในโซน extreme (+1)
        if direction == "BULLISH" and rsi_h1 < 68:
            rsi_h1_valid = True
            score += 1
            details.append(f"H1 RSI {rsi_h1:.0f} — ยังมีที่ให้วิ่งขึ้น")
        elif direction == "BEARISH" and rsi_h1 > 32:
            rsi_h1_valid = True
            score += 1
            details.append(f"H1 RSI {rsi_h1:.0f} — ยังมีที่ให้วิ่งลง")
        else:
            details.append(f"H1 RSI {rsi_h1:.0f} อยู่ในโซน extreme — entry ไม่ดี")
    else:
        details.append("ไม่มีข้อมูล H1")

    # ── 3. M30 (primary) / M15 (fallback): trigger confirmation (max +1) ───
    # M30 clean กว่า M15 — ใช้ M30 ก่อน ถ้าไม่มีค่อย fallback M15
    trigger_df   = _to_df(ohlcv_dict.get("M30", [])) or _to_df(ohlcv_dict.get("M15", []))
    trigger_label = "M30" if _to_df(ohlcv_dict.get("M30", [])) is not None else "M15"
    m15_confirmed = False

    if trigger_df is not None:
        close_t   = trigger_df["close"]
        rsi_t_s   = _rsi(close_t)
        rsi_t     = float(rsi_t_s.iloc[-1])
        rsi_prev  = float(rsi_t_s.iloc[-2]) if len(rsi_t_s) >= 2 else rsi_t

        if direction == "BULLISH" and rsi_t > 45 and rsi_t >= rsi_prev:
            m15_confirmed = True
            score += 1
            details.append(f"{trigger_label} RSI {rsi_t:.0f} กลับขึ้น — momentum ยืนยัน")
        elif direction == "BEARISH" and rsi_t < 55 and rsi_t <= rsi_prev:
            m15_confirmed = True
            score += 1
            details.append(f"{trigger_label} RSI {rsi_t:.0f} กลับลง — momentum ยืนยัน")
        else:
            details.append(f"{trigger_label} RSI {rsi_t:.0f} ยังไม่ยืนยันทิศทาง")
    else:
        details.append("ไม่มีข้อมูล M15")

    # ── Setup type label ───────────────────────────────────────────────────
    if h4_aligned and near_level and m15_confirmed:
        setup_type = "Reversal + M15 Confirm" if is_reversal else "EMA Pullback + M15 Confirm"
    elif h4_aligned and near_level and not m15_confirmed:
        setup_type = "Reversal Zone (รอ M15 ยืนยัน)" if is_reversal else "Pullback Zone (รอ M15 ยืนยัน)"
    elif h4_aligned and not_overextended and m15_confirmed:
        setup_type = "Trend Continuation"
    elif h4_aligned and not near_level:
        setup_type = "Reversal (H4 Extreme)" if is_reversal else "รอ Pullback ก่อนเข้า"
    elif not h4_aligned:
        setup_type = "H4 ขัดแย้ง — ไม่เข้า"
    else:
        setup_type = "No Clear Setup"

    if score >= 5:
        quality = "HIGH"
    elif score >= 4:
        quality = "MEDIUM"
    else:
        quality = "LOW"

    return {
        "score": score,
        "max_score": 6,
        "quality": quality,
        "setup_type": setup_type,
        "details": details,
        "entry_zone": entry_zone,
        "h4_aligned": h4_aligned,
        "is_reversal": is_reversal,
        "near_level": near_level,
        "m15_confirmed": m15_confirmed,
    }
