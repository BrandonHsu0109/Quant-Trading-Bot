# strategies/breakout_scalping.py
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import config
from .base import Strategy

NY_TZ = ZoneInfo("America/New_York")

_open = {}   # pair -> {"entry":float, "atr":float, "sl":float, "tp":float, "ts":datetime}
_cool = {}   # pair -> cooldown_until_utc (datetime)


def _post_cap(weights: dict[str, float], cap: float) -> dict[str, float]:
    if not weights:
        return {}
    w = {k: max(min(v, cap), -cap) for k, v in weights.items()}
    s = sum(abs(v) for v in w.values())
    if s <= 1e-9:
        return {}
    return w


def _floor_5m(dt_utc: datetime) -> datetime:
    dt_ny = dt_utc.astimezone(NY_TZ)
    m = (dt_ny.minute // 5) * 5
    flo = datetime(dt_ny.year, dt_ny.month, dt_ny.day, dt_ny.hour, m, tzinfo=NY_TZ)
    return flo.astimezone(timezone.utc)


def _downsample_to_5m(dq, max_bars: int = 300):
    if not dq:
        return []

    buckets = {}

    for rec in dq:
        if len(rec) == 3:
            ts, px, vol = rec
        elif len(rec) == 2:
            ts, px = rec
            vol = 0.0
        else:
            continue

        bar_start = _floor_5m(ts)
        bar_end = bar_start + timedelta(minutes=5)

        if bar_end not in buckets:
            buckets[bar_end] = {"close": px, "vol": float(vol), "ts": ts}
        else:
            buckets[bar_end]["close"] = px
            buckets[bar_end]["vol"] += float(vol)
            buckets[bar_end]["ts"] = ts

    bars = sorted(
        [(k, v["close"], v["vol"]) for k, v in buckets.items()],
        key=lambda x: x[0],
    )
    if len(bars) > max_bars:
        bars = bars[-max_bars:]
    return bars


def _atr_from_closes(closes, n=14):
    if len(closes) < n + 1:
        return None
    trs = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    atr = sum(trs[:n]) / n
    for tr in trs[n:]:
        atr = (atr * (n - 1) + tr) / n
    return atr


class BreakoutScalping(Strategy):

    def __init__(self, allow_short: bool, params: dict | None = None):
        super().__init__("breakout_scalping", allow_short=False, params=params or {})

        p = self.params
        self.lookback_bars = int(p.get("lookback_bars", p.get("lookback_min", 12)))
        self.range_eps = float(p.get("range_eps", 0.004))
        self.trig_eps = float(p.get("trig_eps", 0.0005))
        self.vol_mult = float(p.get("vol_mult", 1.5))
        self.atr_n = int(p.get("atr_n", 14))
        self.sl_mult = float(p.get("sl_mult", 1.0))   
        self.tp_mult = float(p.get("tp_mult", 2.0))   
        self.timeout_min = int(p.get("timeout_min", 30))
        self.cooldown_min = int(p.get("cooldown_min", 60))
        self.trade_alloc = float(p.get("trade_allocation_pct", 0.25))
        self.min_liq = float(p.get("min_liq", 0.0))

    def target_weights(self, data_handler, prices, liquidity):
        desired = {}
        now_utc = datetime.now(timezone.utc)

        def is_bar_close(pair: str) -> bool:
            if hasattr(data_handler, "is_5m_bar_close"):
                return data_handler.is_5m_bar_close(pair)
            return True

        for pair, dq in data_handler.buffers.items():
            if self.min_liq > 0 and dq:
                last_rec = dq[-1]
                last_vol = last_rec[2] if len(last_rec) >= 3 else 0.0
                if last_vol < self.min_liq:
                    continue

            bars = _downsample_to_5m(
                dq,
                max_bars=max(300, self.atr_n + self.lookback_bars + 10),
            )
            if len(bars) < max(self.atr_n + self.lookback_bars + 1, 20):
                continue

            bar_closed = is_bar_close(pair)

            closes = [b[1] for b in bars]
            vols = [b[2] for b in bars]
            last_close = closes[-1]
            last_vol = vols[-1]

            atr = _atr_from_closes(closes, n=self.atr_n)
            if atr is None or atr <= 0:
                continue

            look = self.lookback_bars
            rng_closes = closes[-look - 1 : -1]
            hi = max(rng_closes)
            lo = min(rng_closes)
            mid = (hi + lo) / 2.0 if (hi and lo) else None
            if mid is None or mid <= 0:
                continue
            range_pct = (hi - lo) / mid

            vol_window = vols[-look - 1 : -1]
            avg_vol = sum(vol_window) / max(1, len(vol_window))
            if avg_vol <= 0:
                volume_ok = True   
            else:
                volume_ok = last_vol > self.vol_mult * avg_vol

            pos = _open.get(pair)

            if pos:
                px = last_close
                entry, sl, tp, ts_entry = (
                    pos["entry"],
                    pos["sl"],
                    pos["tp"],
                    pos["ts"],
                )
                timeout_at = ts_entry + timedelta(minutes=self.timeout_min)

                should_exit = False
                reason = ""

                if px <= sl:
                    should_exit = True
                    reason = "hit SL"
                elif px >= tp:
                    should_exit = True
                    reason = "hit TP"
                elif now_utc >= timeout_at:
                    should_exit = True
                    reason = "timeout"

                if should_exit:
                    logging.info(
                        f"[breakout_scalping] exit {pair} px={px:.6f} entry={entry:.6f} "
                        f"sl={sl:.6f} tp={tp:.6f} reason={reason}"
                    )
                    _open.pop(pair, None)
                    _cool[pair] = now_utc + timedelta(minutes=self.cooldown_min)
                else:
                    desired[pair] = min(
                        self.trade_alloc,
                        getattr(config, "MAX_POSITION_PER_SYMBOL", 0.35),
                    )

            if not bar_closed:
                continue

            if not pos:
                cd_until = _cool.get(pair)
                if cd_until and now_utc < cd_until:
                    continue
                
                if range_pct <= self.range_eps:
                    th_up = hi * (1.0 + self.trig_eps)
                    if (last_close > th_up) and volume_ok:
                        entry = last_close
                        sl = entry - self.sl_mult * atr
                        tp = entry + self.tp_mult * atr
                        _open[pair] = {
                            "entry": entry,
                            "atr": atr,
                            "sl": sl,
                            "tp": tp,
                            "ts": now_utc,
                        }
                        w = min(
                            self.trade_alloc,
                            getattr(config, "MAX_POSITION_PER_SYMBOL", 0.35),
                        )
                        desired[pair] = w
                        logging.info(
                            f"[breakout_scalping] entry {pair} entry={entry:.6f} atr={atr:.6f} "
                            f"sl={sl:.6f} tp={tp:.6f} w={w:.3f}"
                        )

        desired = _post_cap(
            desired,
            cap=getattr(config, "MAX_POSITION_PER_SYMBOL", 0.35),
        )
        return desired


def build(allow_short: bool, params: dict | None = None):
    return BreakoutScalping(allow_short=False, params=params)
