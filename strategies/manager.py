# startegies/manager.py
import importlib
import logging
import config

def _cap_and_normalize(weights: dict[str, float], cap: float) -> dict[str, float]:
    if not weights:
        return {}
    w = {k: max(min(v, cap), -cap) for k, v in weights.items()}
    total = sum(abs(x) for x in w.values())
    if total <= 1e-12:
        return {}
    if total > 1.0:
        w = {k: v / total for k, v in w.items()}
    return w

class StrategyManager:
    def __init__(self, allow_short: bool):
        self.allow_short = allow_short
        self.strategies = []
        for spec in getattr(config, "STRATEGIES", []):
            name = spec["name"]
            alloc = float(spec.get("alloc", 0.0))
            params = spec.get("params", {})
            mod = importlib.import_module(f"strategies.{name}")
            cls = getattr(mod, "build")
            s = cls(allow_short=self.allow_short, params=params)
            self.strategies.append((s, alloc))

    def combine(self, data_handler, prices: dict[str, float], liquidity: dict[str, float]) -> dict[str, float]:
        total = {}
        debug_on = bool(getattr(config, "DEBUG_LOG_WEIGHTS", False))
        topn = int(getattr(config, "DEBUG_TOP_N", 5))
        if debug_on:
            logging.info("== strategy breakdown begin ==")
        for strat, alloc in self.strategies:
            w = strat.target_weights(data_handler, prices, liquidity)
            if debug_on:
                if not w:
                    logging.info(f"[{strat.name}] no picks")
                else:
                    picks = sorted(w.items(), key=lambda x: abs(x[1]), reverse=True)[:topn]
                    logging.info(f"[{strat.name}] top picks: " + ", ".join(f"{k}:{v:+.3f}" for k,v in picks))
            if not w:
                continue
            for k, v in w.items():
                total[k] = total.get(k, 0.0) + alloc * v
        total = _cap_and_normalize(total, cap=getattr(config, "MAX_POSITION_PER_SYMBOL", 0.35))
        if debug_on:
            if not total:
                logging.info("[final] no combined picks")
            else:
                picks = sorted(total.items(), key=lambda x: abs(x[1]), reverse=True)[:topn]
                logging.info("[final] combined: " + ", ".join(f"{k}:{v:+.3f}" for k,v in picks))
            logging.info("== strategy breakdown end ==")
        return total
