# horus_client.py
from datetime import datetime, timezone
import requests
import config
import logging

SUPPORTED_ASSETS = {
    "BTC","ETH","XRP","BNB","SOL","DOGE","TRX","ADA","XLM","WBTC","SUI","HBAR","LINK","BCH","WBETH",
    "UNI","AVAX","SHIB","TON","LTC","DOT","PEPE","AAVE","ONDO","TAO","WLD","APT","NEAR","ARB","ICP",
    "ETC","FIL","TRUMP","OP","ALGO","POL","BONK","ENA","ENS","VET","SEI","RENDER","FET","ATOM",
    "VIRTUAL","SKY","BNSOL","RAY","TIA","JTO","JUP","QNT","FORM","INJ","STX"
}

FALLBACK_TS_KEYS = ["ts","time","timestamp","t"]
FALLBACK_PX_KEYS = ["price","close","c","p","value"]

# 可在 config.py 自訂要剝除的報價幣後綴；預設含 USD/USDT/USDC
QUOTE_SUFFIXES = getattr(config, "ROOSTOO_QUOTE_SUFFIXES", ["USD","USDT","USDC"])

class HorusClient:
    def __init__(self, url=None, api_key=None):
        self.url = (url or getattr(config, "HORUS_PRICE_URL")).rstrip("/")
        self.api_key = api_key or getattr(config, "HORUS_API_KEY", "")
        self.header_key = getattr(config, "HORUS_HEADER_KEY", "X-API-Key")
        self.asset_key = getattr(config, "HORUS_ASSET_PARAM", "asset")
        self.start_key = getattr(config, "HORUS_START_PARAM", "start")
        self.end_key = getattr(config, "HORUS_END_PARAM", "end")
        self.interval_key = getattr(config, "HORUS_INTERVAL_PARAM", "interval")
        self.interval_val = getattr(config, "HORUS_INTERVAL", "15m")
        self.ts_keys = getattr(config, "HORUS_TS_FIELDS", FALLBACK_TS_KEYS)
        self.px_keys = getattr(config, "HORUS_PRICE_FIELDS", FALLBACK_PX_KEYS)
        self.debug = bool(getattr(config, "DEBUG_HORUS", True))

    def _headers(self):
        return {self.header_key: self.api_key} if self.api_key else {}

    def asset_from_pair(self, pair: str) -> str:
        """
        將 Roostoo 交易對（如 ZEN/USD、ZEN-USD）轉成 Horus 需要的 base（ZEN）。
        會剝除 /USD、-USD（以及 config.ROOSTOO_QUOTE_SUFFIXES 指定的後綴）。
        """
        p = pair.upper()
        p = p.replace("-", "/")              # 統一分隔符
        base = p.split("/")[0]               # 先取 base
        quote = p.split("/")[1] if "/" in p else ""
        # 若帶有標準報價幣後綴，強制剝除
        if quote in QUOTE_SUFFIXES:
            return base
        # 兼容像 "ZEN/USD"、"ZEN/USDT" 以外的奇形：直接剝 /QUOTE
        for q in QUOTE_SUFFIXES:
            suffix1 = f"/{q}"
            if p.endswith(suffix1):
                return p[: -len(suffix1)]
        return base

    def is_supported(self, asset: str) -> bool:
        return asset.upper() in SUPPORTED_ASSETS

    def fetch_range_prices(self, pair: str, start_utc: datetime, end_utc: datetime) -> list[dict]:
        asset = self.asset_from_pair(pair)
        if not self.is_supported(asset):
            if self.debug:
                logging.info(f"[horus] skip unsupported asset {asset} for {pair}")
            return []
        params = {
            self.asset_key: asset,
            self.start_key: int(start_utc.replace(tzinfo=timezone.utc).timestamp()),
            self.end_key: int(end_utc.replace(tzinfo=timezone.utc).timestamp()),
            "format": "json"
        }
        if self.interval_key:
            params[self.interval_key] = self.interval_val
        r = requests.get(self.url, headers=self._headers(), params=params, timeout=10)
        if r.status_code in (400, 404, 422):
            if self.debug:
                logging.info(f"[horus] {pair}->{asset} http={r.status_code} url={r.url}")
            return []
        r.raise_for_status()
        raw = r.json()
        if self.debug and isinstance(raw, list) and raw:
            logging.info(f"[horus] {pair}->{asset} sample_keys={list(raw[0].keys())} n={len(raw)}")
        out = []
        for row in (raw or []):
            ts_val = next((row.get(k) for k in self.ts_keys if k in row), None)
            px_val = next((row.get(k) for k in self.px_keys if k in row), None)
            if ts_val is None or px_val is None:
                continue
            try:
                ts = datetime.fromtimestamp(int(ts_val), tz=timezone.utc)
                out.append({"ts": ts, "price": float(px_val)})
            except Exception:
                continue
        if self.debug:
            logging.info(f"[horus] {pair}->{asset} parsed_rows={len(out)}")
        return out
