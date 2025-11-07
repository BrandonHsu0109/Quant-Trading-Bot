# data_handler.py
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os
import json
import config
import logging

class DataHandler:
    def __init__(self, lookback: int = None):
        self.lookback = lookback or config.LOOKBACK_MINUTES
        self.buffers = defaultdict(lambda: deque(maxlen=max(self.lookback, 6000)))
        self.ny = ZoneInfo("America/New_York")
        self.daily_range_cache = {}
        self.last_bar_index = {}
        self.horus_unsupported = set()


    def update_from_roostoo(self, data: dict):
        now_utc = datetime.now(timezone.utc)
        for pair, info in data.items():
            last_price = float(info.get("LastPrice", 0.0))
            unit_vol = float(info.get("UnitTradeValue", 0.0))
            self.buffers[pair].append((now_utc, last_price, unit_vol))

    def get_latest_price_map(self) -> dict[str, float]:
        out = {}
        for pair, dq in self.buffers.items():
            if dq:
                out[pair] = dq[-1][1]
        return out

    def get_latest_liquidity_map(self) -> dict[str, float]:
        out = {}
        for pair, dq in self.buffers.items():
            if dq:
                out[pair] = dq[-1][2]
        return out

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
        now_utc = dq[-1][0]
        start_utc, end_utc, ny_date = self._first_4h_window_utc(now_utc)
        key = (pair, ny_date)
        if key in self.daily_range_cache:
            hi, lo = self.daily_range_cache[key]
            return hi, lo, str(ny_date)
        if not bool(getattr(config, "STRICT_FIRST4H_ONLY", True)):
            hi = None
            lo = None
            ny_now = now_utc.astimezone(self.ny)
            if ny_now.hour >= 4:
                window_prices = []
                cutoff = now_utc - timedelta(minutes=240)
                for ts, px, _ in dq:
                    if ts >= cutoff:
                        window_prices.append(px)
                if len(window_prices) >= 5:
                    hi = max(window_prices)
                    lo = min(window_prices)
                    self.daily_range_cache[key] = (hi, lo)
                    return hi, lo, str(ny_now.date())
            return None, None, str(ny_date)
        hi = None
        lo = None
        in_window = 0
        for ts, px, _ in dq:
            if start_utc <= ts < end_utc:
                in_window += 1
                hi = px if hi is None else max(hi, px)
                lo = px if lo is None else min(lo, px)
        if hi is not None and lo is not None and in_window >= 2:
            self.daily_range_cache[key] = (hi, lo)
            return hi, lo, str(ny_date)
        return None, None, str(ny_date)

    def first4h_ready(self, pair: str) -> bool:
        hi, lo, _ = self.get_first4h_range(pair)
        return hi is not None and lo is not None

    def ensure_first4h_range_via_horus(self, pair: str, horus_client):
        dq = self.buffers.get(pair)
        if not dq:
            return None, None, None
        now_utc = dq[-1][0]
        start_utc, end_utc, ny_date = self._first_4h_window_utc(now_utc)
        key = (pair, ny_date)
        if key in self.daily_range_cache:
            hi, lo = self.daily_range_cache[key]
            return hi, lo, str(ny_date)
        if not bool(getattr(config, "USE_HORUS_BACKFILL", True)):
            return None, None, str(ny_date)
        if not self.is_after_first4h_close():
            return None, None, str(ny_date)
        end_inclusive = end_utc + timedelta(seconds=60)
        rows = horus_client.fetch_range_prices(pair, start_utc, end_inclusive)
        if not rows:
            logging.info(f"[horus] no rows for {pair} {ny_date}")
            return None, None, str(ny_date)
        hi = max(r["price"] for r in rows)
        lo = min(r["price"] for r in rows)
        self.daily_range_cache[key] = (hi, lo)
        logging.info(f"[horus] backfilled {pair} {ny_date} hi={hi:.6f} lo={lo:.6f}")
        return hi, lo, str(ny_date)

    def is_5m_bar_close(self, pair: str) -> bool:
        dq = self.buffers.get(pair)
        if not dq:
            return False
        ts_utc = dq[-1][0]
        ny_dt = ts_utc.astimezone(self.ny)
        bar_index = (ny_dt.hour * 60 + ny_dt.minute) // 5
        last = self.last_bar_index.get(pair)
        if last is None or bar_index != last:
            self.last_bar_index[pair] = bar_index
            return True
        return False

    def get_5m_close(self, pair: str):
        dq = self.buffers.get(pair)
        if not dq:
            return None
        return dq[-1][1]

    def save_cache(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for pair, dq in self.buffers.items():
                for ts, px, vol in dq:
                    rec = {"pair": pair, "ts": ts.timestamp(), "px": px, "vol": vol}
                    f.write(json.dumps(rec) + "\n")

    def load_cache(self, path: str, max_age_hours: int = 48):
        if not os.path.exists(path):
            return
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        temp = defaultdict(list)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    ts = datetime.fromtimestamp(rec["ts"], tz=timezone.utc)
                    if ts >= cutoff:
                        temp[rec["pair"]].append((ts, float(rec["px"]), float(rec.get("vol", 0.0))))
                except:
                    continue
        for pair, rows in temp.items():
            rows.sort(key=lambda x: x[0])
            dq = self.buffers[pair]
            for r in rows[-self.buffers[pair].maxlen:]:
                dq.append(r)
