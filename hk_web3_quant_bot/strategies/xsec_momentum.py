import config
from .base import Strategy

def _post_cap(weights: dict[str, float], cap: float) -> dict[str, float]:
    if not weights:
        return {}
    w = {k: max(min(v, cap), -cap) for k, v in weights.items()}
    s = sum(abs(v) for v in w.values())
    if s <= 1e-9:
        return {}
    return w

class XSecMomentum(Strategy):
    def __init__(self, allow_short: bool, params: dict | None = None):
        super().__init__("xsec_momentum", allow_short, params)
        self.buffer = {}

    def target_weights(self, data_handler, prices, liquidity):
        mom = {}
        for pair, dq in data_handler.buffers.items():
            if len(dq) < 6:
                continue
            p0 = dq[-6][1]
            p1 = dq[-1][1]
            if p0 > 0:
                mom[pair] = (p1 - p0) / p0
        if not mom:
            return {}
        min_liq = float(self.params.get("min_liq", 0))
        symbols = [s for s in mom.keys() if liquidity.get(s, 0) >= min_liq]
        ranked = sorted(symbols, key=lambda s: mom[s], reverse=True)
        top_k = int(self.params.get("top_k", 2))
        picked = ranked[:top_k]
        if not picked:
            return {}
        w = {s: 1.0 / len(picked) for s in picked}
        return _post_cap(w, cap=getattr(config, "MAX_POSITION_PER_SYMBOL", 0.35))

def build(allow_short: bool, params: dict | None = None):
    return XSecMomentum(allow_short=allow_short, params=params)
