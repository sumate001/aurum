"""
CFTC Commitment of Traders — gold futures positioning (COMEX).
Published weekly (Friday, reflects prior Tuesday's data).
Non-commercial net = speculative sentiment indicator.
Commercial net = hedger/producer positioning (smart money).
"""

import httpx

CFTC_API       = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json"
GOLD_MARKET    = "GOLD - COMMODITY EXCHANGE INC."


def fetch_cftc_positioning() -> dict:
    try:
        resp = httpx.get(
            CFTC_API,
            params={
                "market_and_exchange_names": GOLD_MARKET,
                "$limit":  2,
                "$order":  "report_date_as_yyyy_mm_dd DESC",
            },
            timeout=20,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return {"error": "CFTC returned no gold rows"}

        latest = rows[0]
        prev   = rows[1] if len(rows) > 1 else None

        def _int(val):
            try:
                return int(str(val).replace(",", "").strip())
            except Exception:
                return 0

        spec_long  = _int(latest.get("noncomm_positions_long_all",  0))
        spec_short = _int(latest.get("noncomm_positions_short_all", 0))
        spec_net   = spec_long - spec_short

        comm_long  = _int(latest.get("comm_positions_long_all",  0))
        comm_short = _int(latest.get("comm_positions_short_all", 0))
        comm_net   = comm_long - comm_short

        # week-on-week change — API has pre-calculated change fields
        spec_long_wow  = _int(latest.get("change_in_noncomm_long_all",  0))
        spec_short_wow = _int(latest.get("change_in_noncomm_short_all", 0))
        spec_net_wow   = spec_long_wow - spec_short_wow

        return {
            "report_date":      latest.get("report_date_as_yyyy_mm_dd", ""),
            "market":           latest.get("market_and_exchange_names", GOLD_MARKET),
            "speculator_net":   spec_net,
            "speculator_long":  spec_long,
            "speculator_short": spec_short,
            "speculator_wow":   spec_net_wow,
            "commercial_net":   comm_net,
            "commercial_long":  comm_long,
            "commercial_short": comm_short,
            "bias":             "BULLISH" if spec_net > 0 else "BEARISH",
        }
    except Exception as e:
        return {"error": str(e)}


def format_for_seed(data: dict) -> str:
    if "error" in data:
        return ""
    wow     = data.get("speculator_wow", 0)
    wow_str = f" ({'+' if wow >= 0 else ''}{wow:,} WoW)" if wow else ""
    arrow   = "▲" if data["bias"] == "BULLISH" else "▼"
    return (
        f"## CFTC COT Positioning (as of {data['report_date']})\n"
        f"- Speculator net: **{data['speculator_net']:+,}** contracts{wow_str} → {arrow} {data['bias']}\n"
        f"  Long {data['speculator_long']:,} / Short {data['speculator_short']:,}\n"
        f"- Commercial (hedger) net: {data['commercial_net']:+,} contracts\n"
        f"  Long {data['commercial_long']:,} / Short {data['commercial_short']:,}\n"
    )
