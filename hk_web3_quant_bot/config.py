import os

BASE_URL = os.getenv("ROOSTOO_BASE_URL", "https://mock-api.roostoo.com")
API_KEY = os.getenv("ROOSTOO_API_KEY", "cnbsk0qTgN8a8HxqAPjjSd02TrxFa1QDINYnlQk3IhGdRot0PVf8I2gyaIgxHGEg")
SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY", "kAntm1GT4Snox6iKsUk1v95Q6DreKnXHgqPZzL2Ak9Tsq67tA6BVfE3gfbARTJ9T")

ORDER_INTERVAL_SEC = 60
LOG_FILE = "logs/run.log"
LOG_LEVEL = "INFO"

LOOKBACK_MINUTES = 1200
MIN_24H_VOLUME = 0
MAX_POSITION_PER_SYMBOL = 0.35

TOTAL_CAPITAL_USDT = 10000
MIN_NOTIONAL = 0.1

ALLOW_SHORT = False
STRICT_FIRST4H_ONLY = True

DEBUG_LOG_WEIGHTS = True
DEBUG_TOP_N = 5

STRATEGIES = [
    {
        "name": "four_hr_range",
        "alloc": 0.6,
        "params": {
            "max_r_pct": 0.01,
            "min_r_pct": 0.002,
            "trade_allocation_pct": 0.5
        }
    },
    {
        "name": "xsec_momentum",
        "alloc": 0.4,
        "params": {
            "top_k": 2,
            "min_liq": 0,
            "rebalance_style": "continuous"
        }
    }
]
