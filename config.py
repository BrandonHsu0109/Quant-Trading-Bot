# config.py
import os

BASE_URL = os.getenv("ROOSTOO_BASE_URL", "https://mock-api.roostoo.com")
API_KEY = os.getenv("ROOSTOO_API_KEY", "tyrOB0BUBz83UffRcb4VOynOe3Vf6X8EEcftJJpHmJbMTtX0Qq1QVjjwpy0Z4c3F")          
SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY", "GlnkQIzqTlMCMW4x9Wbs7OcMQqLObcLBkFq7mH8DlbFVXPlLVVwe9SamLtzN1CfJ")    


HORUS_PRICE_URL = "https://api-horus.com/market/price"
HORUS_API_KEY = "ec80096991f2c98f50db2883c492788fe05aaa88740da49bbf060492d6fdd9ec"                                 
HORUS_INTERVAL = "15m"
USE_HORUS_BACKFILL = True

HORUS_HEADER_KEY = "X-API-Key"
HORUS_ASSET_PARAM = "asset"
HORUS_START_PARAM = "start"
HORUS_END_PARAM = "end"
HORUS_INTERVAL_PARAM = "interval"


HORUS_TS_FIELDS = ["ts", "time", "timestamp", "t"]
HORUS_PRICE_FIELDS = ["price", "p", "close", "c"]


ORDER_INTERVAL_SEC = 300          
LOOP_INTERVAL_SEC = ORDER_INTERVAL_SEC   # time interval for main_loop calls


LOG_FILE = "logs/run.log"
LOG_LEVEL = "INFO"


TRADE_LOG_FILE = "logs/trades.csv"   
EQUITY_LOG_FILE = "logs/equity.csv" 


LOOKBACK_MINUTES = 240                       


MIN_24H_VOLUME = 0               
MAX_POSITION_PER_SYMBOL = 0.35   

MIN_NOTIONAL = 10               

ALLOW_SHORT = False
STRICT_FIRST4H_ONLY = True       

DEBUG_LOG_WEIGHTS = True
DEBUG_TOP_N = 5


DRY_RUN = False   # For backtesting, True = simulation, False = real trading on roostoo

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
        "lookback_bars": 12,
        "range_eps": 0.004,
        "trig_eps": 0.0005,
        "vol_mult": 1.5,
        "atr_n": 14,
        "sl_mult": 1.0,
        "tp_mult": 2.0,
        "timeout_min": 30,
        "cooldown_min": 60,
        "trade_allocation_pct": 0.25,
        "min_liq": 0
        }
    }
]

