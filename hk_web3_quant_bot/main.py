# main.py
# -*- coding: utf-8 -*-

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Iterable, Dict, Any, List, Tuple

# =========================
# Logging setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger()
logger.info("Starting Roostoo Quant Bot ...")

# =========================
# Config: Universe
# =========================
UNIVERSE: List[Tuple[str, str]] = [
    ("AAVE/USD", "AAVE"),
    ("ADA/USD", "ADA"),
    ("APT/USD", "APT"),
    ("ARB/USD", "ARB"),
    ("AVAX/USD", "AVAX"),
    ("BNB/USD", "BNB"),
    ("BONK/USD", "BONK"),
    ("BTC/USD", "BTC"),
    ("DOGE/USD", "DOGE"),
    ("DOT/USD", "DOT"),
    ("ENA/USD", "ENA"),
    ("ETH/USD", "ETH"),
    ("FET/USD", "FET"),
    ("FIL/USD", "FIL"),
    ("HBAR/USD", "HBAR"),
    ("ICP/USD", "ICP"),
    ("LINK/USD", "LINK"),
    ("LTC/USD", "LTC"),
    ("NEAR/USD", "NEAR"),
    ("ONDO/USD", "ONDO"),
    ("PEPE/USD", "PEPE"),
    ("POL/USD", "POL"),
    ("SEI/USD", "SEI"),
    ("SHIB/USD", "SHIB"),
    ("SOL/USD", "SOL"),
    ("SUI/USD", "SUI"),
    ("TAO/USD", "TAO"),
    ("TON/USD", "TON"),
    ("TRUMP/USD", "TRUMP"),
    ("TRX/USD", "TRX"),
    ("UNI/USD", "UNI"),
    ("VIRTUAL/USD", "VIRTUAL"),
    ("WLD/USD", "WLD"),
    ("XLM/USD", "XLM"),
    ("XRP/USD", "XRP"),
]

# 只比對「幣種本體」（斜線左邊），避免字串包含誤殺 /USD
UNSUPPORTED_BASE = {
    "1000CHEEMS","ASTER","AVNT","BIO","BMT","CAKE","CFX","CRV",
    "EDEN","EIGEN","FLOKI","HEMI","LINEA","LISTA","MIRA","OPEN",
    "PAXG","PENDLE","PENGU","PLUME","PUMP","S","SOMI","STO",
    "TUT","WIF","WLFI","XPL","ZEC","ZEN"
}

# =========================
# Utils
# =========================
def _to_iso8601_utc(ts) -> str | None:
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:  # 毫秒
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        if isinstance(ts, str):
            if ts.endswith("Z"):
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).isoformat()
            if "+" in ts:
                return datetime.fromisoformat(ts).astimezone(timezone.utc).isoformat()
            return (datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)).isoformat()
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.astimezone(timezone.utc).isoformat()
        return str(ts)
    except Exception:
        return None

def filter_rows_by_day_utc(rows: Iterable[Dict[str, Any]], day_yyyy_mm_dd: str) -> List[Dict[str, Any]]:
    start = datetime.strptime(day_yyyy_mm_dd, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    kept = []
    for r in rows or []:
        ts = r.get("timestamp")
        dt_utc_iso = _to_iso8601_utc(ts)
        if not dt_utc_iso:
            continue
        dt_utc = datetime.fromisoformat(dt_utc_iso)
        if start <= dt_utc < end:
            kept.append(r)
    return kept

def emit_rows_csv(symbol: str, rows: Iterable[Dict[str, Any]]) -> None:
    for r in rows or []:
        ts_iso = _to_iso8601_utc(r.get("timestamp"))
        price = r.get("price")
        if ts_iso is None or price is None:
            continue
        print(f"{symbol},{ts_iso},{price}")

def process_and_emit(symbol: str, raw_rows: Iterable[Dict[str, Any]] | None, day_yyyy_mm_dd: str, fallback_last_n: int = 20) -> int:
    raw_rows = list(raw_rows or [])
    picked = filter_rows_by_day_utc(raw_rows, day_yyyy_mm_dd)
    if not picked and raw_rows:
        picked = raw_rows[-fallback_last_n:]
    emit_rows_csv(symbol, picked)
    return len(picked)

# =========================
# Data source hook（把你的 ROOSTOO/Horus 抓價接進來）
# =========================
def get_price_rows(symbol_pair: str) -> List[Dict[str, Any]]:
    """
    回傳 list[dict]，每列至少含 {'timestamp': ..., 'price': ...}
    TODO: 這裡接你原本從 ROOSTOO 取數的函式，保持鍵名 timestamp / price。
    """
    return []  # 先留空；接好後就會有輸出

# =========================
# Normalization
# =========================
def normalize_rows_to_tp(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        ts = r.get("timestamp")
        px = r.get("price")
        if px is None:
            continue
        try:
            price_f = float(px)
        except Exception:
            continue
        out.append({"timestamp": ts, "price": price_f})
    return out

# =========================
# Strategy placeholders
# =========================
def strategies_breakdown(today_utc: str, processed_symbols: List[Tuple[str,str]]) -> None:
    logger.info("== strategy breakdown begin ==")
    logger.info("[four_hr_range] no picks")
    logger.info("[xsec_momentum] no picks")
    logger.info("[final] no combined picks")
    logger.info("== strategy breakdown end ==")

# =========================
# Per-symbol handler
# =========================
def handle_symbol(symbol_pair: str, internal_symbol: str, day_utc_str: str) -> None:
    rows = get_price_rows(symbol_pair)

    sample_keys = []
    n = 0
    if rows:
        sample_keys = list(rows[0].keys())[:2]
        n = len(rows)
    logger.info("[horus] %s->%s sample_keys=%s n=%d", symbol_pair, internal_symbol, sample_keys or ['timestamp','price'], n)

    parsed_rows = normalize_rows_to_tp(rows)
    logger.info("[horus] %s->%s parsed_rows=%d", symbol_pair, internal_symbol, len(parsed_rows))
    if not parsed_rows:
        logger.info("[horus] no rows for %s %s", symbol_pair, day_utc_str)

    try:
        process_and_emit(internal_symbol, parsed_rows, day_utc_str, fallback_last_n=20)
    except Exception as e:
        logger.exception("emit csv failed for %s: %s", internal_symbol, e)

# =========================
# Main
# =========================
def main():
    today_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    processed: List[Tuple[str, str]] = []

    for symbol_pair, internal_symbol in UNIVERSE:
        base = symbol_pair.split("/")[0]  # 只取幣種，不含 /USD
        if base in UNSUPPORTED_BASE:
            logger.info("[horus] skip unsupported asset %s for %s", base, symbol_pair)
            logger.info("[horus] no rows for %s %s", symbol_pair, today_utc_str)
            continue

        handle_symbol(symbol_pair, internal_symbol, today_utc_str)
        processed.append((symbol_pair, internal_symbol))

    strategies_breakdown(today_utc_str, processed)

if __name__ == "__main__":
    main()
