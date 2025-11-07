# emit_csv.py
# -*- coding: utf-8 -*-

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Iterable, Dict, Any, List

def _to_iso8601_utc(ts) -> str | None:
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:
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

def process_and_emit(
    symbol: str,
    raw_rows: Iterable[Dict[str, Any]] | None,
    day_yyyy_mm_dd: str,
    fallback_last_n: int = 20
) -> int:
    
    raw_rows = list(raw_rows or [])
    picked = filter_rows_by_day_utc(raw_rows, day_yyyy_mm_dd)
    if not picked and raw_rows:
        picked = raw_rows[-fallback_last_n:]
    emit_rows_csv(symbol, picked)
    return len(picked)
