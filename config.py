# config.py
import os

# Roostoo API
BASE_URL = os.getenv("ROOSTOO_BASE_URL", "https://mock-api.roostoo.com")
API_KEY = os.getenv("ROOSTOO_API_KEY", "cnbsk0qTgN8a8HxqAPjjSd02TrxFa1QDINYnlQk3IhGdRot0PVf8I2gyaIgxHGEg")          
SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY", "kAntm1GT4Snox6iKsUk1v95Q6DreKnXHgqPZzL2Ak9Tsq67tA6BVfE3gfbARTJ9T")    

# Horus API
HORUS_PRICE_URL = "https://api-horus.com/market/price"
HORUS_API_KEY = "ec80096991f2c98f50db2883c492788fe05aaa88740da49bbf060492d6fdd9ec"                                 
HORUS_INTERVAL = "15m"
USE_HORUS_BACKFILL = True

HORUS_HEADER_KEY = "X-API-Key"
HORUS_ASSET_PARAM = "asset"
HORUS_START_PARAM = "start"
HORUS_END_PARAM = "end"
HORUS_INTERVAL_PARAM = "interval"

# timestamp/price format from Horus
HORUS_TS_FIELDS = ["ts", "time", "timestamp", "t"]
HORUS_PRICE_FIELDS = ["price", "p", "close", "c"]

# parameters and stake control
ORDER_INTERVAL_SEC = 300          
LOOP_INTERVAL_SEC = ORDER_INTERVAL_SEC   # time interval for main_loop calls

LOG_FILE = "logs/run.log"
LOG_LEVEL = "INFO"

TRADE_LOG_FILE = "logs/trades.csv"   
EQUITY_LOG_FILE = "logs/equity.csv" 

LOOKBACK_MINUTES = 240                       

MIN_24H_VOLUME = 0               # four_hr_range 的流動性篩選，暫時設 0 = 不篩
MAX_POSITION_PER_SYMBOL = 0.35   # 單一幣種最大權重上限

MIN_NOTIONAL = 0.1               # 單筆最小交易名目金額（USDT）

ALLOW_SHORT = False
STRICT_FIRST4H_ONLY = True       # four_hr_range strategy only starts trading after 4:00 NY time every day

DEBUG_LOG_WEIGHTS = True
DEBUG_TOP_N = 5


DRY_RUN = False   # For backtesting, True = simulation, False = real trading on roostoo

# strategies that are applied
STRATEGIES = [
    {
        "name": "four_hr_range",
        "alloc": 0.5,
        "params": {
            "max_r_pct": 0.01,
            "min_r_pct": 0.002,
            "trade_allocation_pct": 0.5
        }
    },
    {
        "name": "breakout_scalping",
        "alloc": 0.3,
        "params": {
            "lookback_min": 5,          # 觀察窗
            "trig_eps": 0.001,           # 突破幅度 0.1%
            "sl_mult": 0.6,              # 停損 = entry - 0.6 * range
            "tp_mult": 0.8,              # 停利 = entry + 0.8 * range
            "timeout_min": 10,           # 逾時強平
            "cooldown_min": 5,           # 冷卻
            "trade_allocation_pct": 0.25,# 單幣配重（策略內部 cap 前）
            "min_liq": 0                 # 如需用 UnitTradeValue 當門檻可設值
        }
    }
]

