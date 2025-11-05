from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import config

class DataHandler:
    def __init__(self, lookback: int = None):
        self.lookback = lookback or config.LOOKBACK_MINUTES
        self.buffers = defaultdict(lambda: deque(maxlen=max(self.lookback, 6000)))
        self.ny = ZoneInfo("America/New_York")
        self.daily_range_cache = {}
        self.last_bar_index = {}

    def update_from_roostoo(self, data: dict):
        now_utc = datetime.now(timezone.utc)
        for pair, info in data.items():
            last_price = float(info.get("LastPrice", 0.0))
            unit_vol = float(info.get("UnitTradeValue", 0.0))
            self.buffers[pair].append((now_utc, last_price, unit_vol))

    def get_latest_price_map(self) -> dict[str, float]:
        prices = {}
        for pair, dq in self.buffers.items():
            if dq:
                prices[pair] = dq[-1][1]
        return prices

    def get_latest_liquidity_map(self) -> dict[str, float]:
        liq = {}
        for pair, dq in self.buffers.items():
            if dq:
                liq[pair] = dq[-1][2]
        return liq

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
        if not self.is_after_first4h_close():
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
