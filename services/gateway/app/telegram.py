import asyncio
import logging
import os
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .approval import get_signal, get_recent_signals, update_signal_status
from .mt5_client import execute_order

log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_app: Optional[Application] = None


def _format_signal(signal: dict, signal_id: str) -> str:
    action = signal.get("action", "?")
    emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
    macro = signal.get("macro_bias", "?")
    macro_emoji = "🟢" if macro == "BULLISH" else "🔴" if macro == "BEARISH" else "⚪"

    upcoming = signal.get("upcoming_events") or []
    event_warn = ""
    if upcoming and isinstance(upcoming, list) and len(upcoming) > 0:
        ev = upcoming[0] if isinstance(upcoming[0], dict) else {}
        if ev:
            event_warn = f"\n⚠️ {ev.get('event_name', '')} in {ev.get('minutes_away', '?')} min"

    sid_short = str(signal_id)[:8]
    return (
        f"{emoji} AURUM SIGNAL #{sid_short}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Pair    : {signal.get('symbol', 'GOLD#')} (XM)\n"
        f"Action  : {action}\n"
        f"TF      : {signal.get('timeframe', '?')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Entry   : {signal.get('entry', '?'):,.2f}\n"
        f"SL      : {signal.get('sl', '?'):,.2f}\n"
        f"TP1     : {signal.get('tp1', '?'):,.2f}\n"
        f"TP2     : {signal.get('tp2', '?'):,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Confidence  : {signal.get('confidence', '?')}%\n"
        f"Macro bias  : {macro_emoji} {macro} ({signal.get('macro_confidence', '?')}%)\n"
        f"Tech agents : {signal.get('technical_consensus', '?')}\n"
        f"━━━━━━━━━━━━━━━━━━━━{event_warn}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 {(signal.get('reasoning') or '')[:120]}"
    )


async def send_signal(signal: dict, signal_id: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured, skipping notification")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    text = _format_signal(signal, signal_id)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve:{signal_id}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject:{signal_id}"),
        ]
    ])
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard)


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if ":" not in data:
        return

    action, signal_id = data.split(":", 1)
    signal = get_signal(signal_id)
    if not signal:
        await query.edit_message_text("Signal not found.")
        return

    if action == "approve":
        update_signal_status(signal_id, "APPROVED")
        try:
            result = execute_order(signal)
            update_signal_status(signal_id, "EXECUTED")
            await query.edit_message_text(f"✅ APPROVED & EXECUTED\nTicket: {result.get('ticket')}")
        except Exception as e:
            log.error("MT5 execution failed: %s", e)
            await query.edit_message_text(f"✅ APPROVED but execution failed:\n{e}")
    elif action == "reject":
        update_signal_status(signal_id, "REJECTED")
        await query.edit_message_text("❌ REJECTED")


async def _cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    signals = get_recent_signals(1)
    if not signals:
        await update.message.reply_text("No signals yet.")
        return
    s = signals[0]
    await update.message.reply_text(
        f"Last signal: {s['action']} | Confidence: {s['confidence']}% | Status: {s['status']}"
    )


async def _cmd_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import httpx
    try:
        resp = httpx.get("http://aurum-ff-scraper:5000/api/calendar", timeout=10)
        events = resp.json().get("events", [])[:5]
        if not events:
            await update.message.reply_text("No upcoming events.")
            return
        lines = [f"📅 {e['event_name']} ({e['currency']}) — {e.get('event_datetime', '?')}" for e in events]
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("status", _cmd_status))
    app.add_handler(CommandHandler("calendar", _cmd_calendar))
    app.add_handler(CallbackQueryHandler(_handle_callback))
    return app
