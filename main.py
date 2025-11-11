# main.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import time
import os
import csv
from datetime import datetime, timezone, timedelta
from typing import Iterable, Dict, Any, List, Tuple
from collections import defaultdict, deque
from zoneinfo import ZoneInfo

import config
from horus_client import HorusClient
from strategies.manager import StrategyManager
from exchange_client import ExchangeClient
from portfolio import calc_rebalance_orders
from execution import execute_orders


logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger()
logger.info("Starting Roostoo Quant Bot ...")


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

def _to_iso8601_utc(ts) -> str | None:
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:  # 毫秒轉秒
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
    kept: List[Dict[str, Any]] = []
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


def process_and_emit(
    symbol: str,
    raw_rows: Iterable[Dict[str, Any]] | None,
    day_yyyy_mm_dd: str,
    fallback_last_n: int = 20,
) -> int:
    raw_rows = list(raw_rows or [])
    picked = filter_rows_by_day_utc(raw_rows, day_yyyy_mm_dd)
    if not picked and raw_rows:
        picked = raw_rows[-fallback_last_n:]
    emit_rows_csv(symbol, picked)
    return len(picked)


def normalize_rows_to_tp(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        ts = r.get("timestamp")
        px = r.get("price")
        if px is None or ts is None:
            continue
        try:
            price_f = float(px)
        except Exception:
            continue
        out.append({"timestamp": ts, "price": price_f})
    return out

class LiveDataHandler:
    def __init__(self, maxlen: int = 1000):
        self.buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=maxlen))
        self.ny = ZoneInfo("America/New_York")
        self.first4h_cache: dict[tuple[str, str], tuple[float, float]] = {}

    def _to_dt_utc(self, ts) -> datetime | None:
        try:
            if isinstance(ts, (int, float)):
                if ts > 1e12:
                    ts = ts / 1000.0
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            if isinstance(ts, str):
                if ts.endswith("Z"):
                    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                if "+" in ts:
                    return datetime.fromisoformat(ts).astimezone(timezone.utc)
                return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    return ts.replace(tzinfo=timezone.utc)
                return ts.astimezone(timezone.utc)
            return None
        except Exception:
            return None

    def update_series(self, pair: str, rows: List[Dict[str, Any]]) -> None:
        dq = self.buffers[pair]
        dq.clear()
        for r in sorted(rows, key=lambda x: x["timestamp"]):
            dt = self._to_dt_utc(r["timestamp"])
            if dt is None:
                continue
            dq.append((dt, r["price"]))

    def _first_4h_window_utc(self, any_utc: datetime):
        ny_dt = any_utc.astimezone(self.ny)
        start_ny = datetime(ny_dt.year, ny_dt.month, ny_dt.day, 0, 0, tzinfo=self.ny)
        end_ny = start_ny + timedelta(hours=4)
        return start_ny.astimezone(timezone.utc), end_ny.astimezone(timezone.utc), start_ny.date()

    def is_after_first4h_close(self) -> bool:
        now_utc = datetime.now(timezone.utc)
        ny_dt = now_utc.astimezone(self.ny)
        return ny_dt.hour >= 4

    def get_first4h_range(self, pair: str):
        dq = self.buffers.get(pair)
        if not dq:
            return None, None, None
        last_ts = dq[-1][0]
        start_utc, end_utc, ny_date = self._first_4h_window_utc(last_ts)
        key = (pair, ny_date)
        if key in self.first4h_cache:
            hi, lo = self.first4h_cache[key]
            return hi, lo, str(ny_date)
        hi = None
        lo = None
        for ts, px in dq:
            if start_utc <= ts < end_utc:
                hi = px if hi is None else max(hi, px)
                lo = px if lo is None else min(lo, px)
        if hi is not None and lo is not None:
            self.first4h_cache[key] = (hi, lo)
            return hi, lo, str(ny_date)
        return None, None, str(ny_date)

    def first4h_ready(self, pair: str) -> bool:
        hi, lo, _ = self.get_first4h_range(pair)
        return hi is not None and lo is not None

    def is_5m_bar_close(self, pair: str) -> bool:
        return True

    def get_5m_close(self, pair: str):
        dq = self.buffers.get(pair)
        if not dq:
            return None
        return dq[-1][1]


_horus_client = HorusClient()
_exchange_client = ExchangeClient()
_strategy_manager = StrategyManager(allow_short=config.ALLOW_SHORT)

def get_price_rows(symbol_pair: str) -> List[Dict[str, Any]]:
    end = datetime.now(timezone.utc)
    lookback_hours = getattr(config, "LOOKBACK_HOURS", 24)
    start = end - timedelta(hours=lookback_hours)
    return _horus_client.fetch_range_prices(symbol_pair, start, end)

EQUITY_LOG_FILE = getattr(config, "EQUITY_LOG_FILE", "logs/equity.csv")

def log_equity_snapshot(total_equity: float, usd_free: float):
    try:
        if EQUITY_LOG_FILE:
            os.makedirs(os.path.dirname(EQUITY_LOG_FILE), exist_ok=True)
            file_exists = os.path.exists(EQUITY_LOG_FILE)
            with open(EQUITY_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if not file_exists:
                    w.writerow(["ts", "equity", "cash"])
                w.writerow([
                    datetime.now(timezone.utc).isoformat(),
                    f"{total_equity:.8f}",
                    f"{usd_free:.8f}",
                ])
    except Exception as e:
        logging.error(f"failed to append equity log: {e}")

def run_once():
    today_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    data_handler = LiveDataHandler()
    prices: dict[str, float] = {}
    liquidity: dict[str, float] = {}

    for symbol_pair, internal_symbol in UNIVERSE:
        rows = get_price_rows(symbol_pair)

        sample_keys = []
        n = 0
        if rows:
            sample_keys = list(rows[0].keys())[:2]
            n = len(rows)
        logger.info(
            "[horus] %s->%s sample_keys=%s n=%d",
            symbol_pair,
            internal_symbol,
            sample_keys or ["timestamp", "price"],
            n,
        )

        parsed_rows = normalize_rows_to_tp(rows)
        logger.info(
            "[horus] %s->%s parsed_rows=%d",
            symbol_pair,
            internal_symbol,
            len(parsed_rows),
        )
        if not parsed_rows:
            logger.info("[horus] no rows for %s %s", symbol_pair, today_utc_str)
            continue

        try:
            process_and_emit(
                internal_symbol, parsed_rows, today_utc_str, fallback_last_n=20
            )
        except Exception as e:
            logger.exception("emit csv failed for %s: %s", internal_symbol, e)

        data_handler.update_series(symbol_pair, parsed_rows)
        last_price = parsed_rows[-1]["price"]
        prices[symbol_pair] = last_price
        liquidity[symbol_pair] = 1e12 

    strat_mgr = StrategyManager(allow_short=config.ALLOW_SHORT)
    target_weights = strat_mgr.combine(data_handler, prices, liquidity)
    logger.info("target_weights: %s", target_weights)

    if not target_weights:
        logger.info("no target weights, skip rebalance this run")
        return
    
    ex_client = ExchangeClient()
    positions, equity, usd_free = ex_client.get_positions_and_equity(prices)

    logger.info("current positions: %s, equity=%.2f, cash=%.2f", positions, equity, usd_free)

    log_equity_snapshot(equity, usd_free)

    orders = calc_rebalance_orders(
        current_positions=positions,
        prices=prices,
        target_weights=target_weights,
        total_equity=equity,
        min_notional=getattr(config, "MIN_NOTIONAL", 0.1),
    )

    if not orders:
        logger.info("no rebalance orders; portfolio already aligned with target")
        return

    logger.info("proposed orders: %s", orders)

    if getattr(config, "DRY_RUN", True):
        logger.info("[DRY_RUN] skip sending orders")
    else:
        execute_orders(ex_client, orders, retry=1)

def main_loop():
    interval_sec = getattr(config, "LOOP_INTERVAL_SEC", getattr(config, "ORDER_INTERVAL_SEC", 60))
    logger.info(f"Starting main loop, interval={interval_sec} sec, DRY_RUN={getattr(config, 'DRY_RUN', True)}")
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("run_once failed")
        time.sleep(interval_sec)


if __name__ == "__main__":
    main_loop()
