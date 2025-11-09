# four_hr_range.py
import logging
import config
from .base import Strategy
from datetime import datetime, timezone

_state = {}
_open = {}

def _apply_r_bounds(entry: float, sl: float, max_r: float, min_r: float):
    r_abs = abs(entry - sl)
    r_pct = r_abs / max(entry, 1e-12)
    if max_r > 0 and r_pct > max_r:
        sl = entry * (1.0 - max_r)
        r_abs = abs(entry - sl)
    if min_r > 0 and r_pct < min_r:
        sl = entry * (1.0 - min_r)
        r_abs = abs(entry - sl)
    if r_abs <= 0:
        return None, None
    tp = entry + 2 * r_abs
    return sl, tp

def _post_cap(weights: dict[str, float], cap: float) -> dict[str, float]:
    if not weights:
        return {}
    w = {k: max(min(v, cap), -cap) for k, v in weights.items()}
    s = sum(abs(v) for v in w.values())
    if s <= 1e-9:
        return {}
    return w

class FourHrRange(Strategy):
    def __init__(self, allow_short: bool, params: dict | None = None):
        super().__init__("four_hr_range", False, params)

    def target_weights(self, data_handler, prices, liquidity):
        desired = {}
        alloc = float(self.params.get("trade_allocation_pct", 0.5))
        max_r = float(self.params.get("max_r_pct", getattr(config, "MAX_R_PCT", 0.01)))
        min_r = float(self.params.get("min_r_pct", getattr(config, "MIN_R_PCT", 0.002)))
        strict = bool(getattr(config, "STRICT_FIRST4H_ONLY", True))
        
        for pair in list(prices.keys()):
            now = datetime.now(timezone.utc)
            if bool(getattr(config, "STRICT_FIRST4H_ONLY", True)):
                if not data_handler.is_after_first4h_close() or not data_handler.first4h_ready(pair):
                    logging.info(f"[four_hr_range] gate: after4h={data_handler.is_after_first4h_close()} ready={data_handler.first4h_ready(pair)} skip {pair} @ {now.isoformat()}")
                    continue
            if strict and not data_handler.is_after_first4h_close():
                continue
            if strict and not data_handler.first4h_ready(pair):
                continue
            hi, lo, ny_date = data_handler.get_first4h_range(pair)
            if hi is None or lo is None or ny_date is None:
                continue
            if not data_handler.is_5m_bar_close(pair):
                continue
            close = data_handler.get_5m_close(pair)
            if close is None:
                continue
            st = _state.get(pair, {"broken": None, "day": ny_date})
            if st["day"] != ny_date:
                st = {"broken": None, "day": ny_date}
                _open.pop(pair, None)
            if st["broken"] is None:
                if close < lo:
                    st["broken"] = ("down", close)
            else:
                dirc, brk_px = st["broken"]
                if dirc == "down" and close >= lo and pair not in _open:
                    entry = close
                    sl0 = min(brk_px, lo)
                    adj = _apply_r_bounds(entry, sl0, max_r, min_r)
                    if adj[0] is not None:
                        sl, tp = adj
                        _open[pair] = {"entry": entry, "sl": sl, "tp": tp, "day": ny_date, "w": abs(alloc)}
                        logging.info(f"[four_hr_range] entry {pair} entry={entry:.6f} sl={sl:.6f} tp={tp:.6f} w={alloc:.3f}")
                    st["broken"] = None
            _state[pair] = st
        to_remove = []
        for pair, meta in list(_open.items()):
            px = prices.get(pair)
            if px is None:
                continue
            if px <= meta["sl"] or px >= meta["tp"] or meta.get("day") != _state.get(pair, {}).get("day"):
                logging.info(f"[four_hr_range] exit {pair} px={px:.6f} sl={meta['sl']:.6f} tp={meta['tp']:.6f}")
                to_remove.append(pair)
            else:
                desired[pair] = meta["w"]
        for pair in to_remove:
            _open.pop(pair, None)
        if liquidity:
            desired = {p: w for p, w in desired.items() if liquidity.get(p, 0) >= config.MIN_24H_VOLUME}
        return _post_cap(desired, cap=getattr(config, "MAX_POSITION_PER_SYMBOL", 0.35))

def build(allow_short: bool, params: dict | None = None):
    return FourHrRange(allow_short=False, params=params)
