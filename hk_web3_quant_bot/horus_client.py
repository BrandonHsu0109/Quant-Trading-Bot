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

# 這是我們認得的 timestamp / price 欄位名稱
FALLBACK_TS_KEYS = ["timestamp", "ts", "time", "t"]
FALLBACK_PX_KEYS = ["price", "close", "c", "p", "value"]

# 可在 config.py 自訂要剝除的報價幣後綴；預設含 USD/USDT/USDC
QUOTE_SUFFIXES = getattr(config, "ROOSTOO_QUOTE_SUFFIXES", ["USD", "USDT", "USDC"])

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

        # 🔴重點1：把 config 裡的欄位名字跟 fallback 合併起來，避免 config 寫錯就找不到欄位
        cfg_ts = getattr(config, "HORUS_TS_FIELDS", None)
        if cfg_ts:
            self.ts_keys = list(dict.fromkeys(list(cfg_ts) + FALLBACK_TS_KEYS))
        else:
            self.ts_keys = FALLBACK_TS_KEYS

        cfg_px = getattr(config, "HORUS_PRICE_FIELDS", None)
        if cfg_px:
            self.px_keys = list(dict.fromkeys(list(cfg_px) + FALLBACK_PX_KEYS))
        else:
            self.px_keys = FALLBACK_PX_KEYS

        self.debug = bool(getattr(config, "DEBUG_HORUS", True))

    def _headers(self):
        return {self.header_key: self.api_key} if self.api_key else {}

    def asset_from_pair(self, pair: str) -> str:
        """
        Roostoo 交易對（如 BTC/USD, BTC-USDT）轉成 base（BTC）。
        """
        p = pair.upper().replace("-", "/")
        base = p.split("/")[0]
        quote = p.split("/")[1] if "/" in p else ""
        if quote in QUOTE_SUFFIXES:
            return base
        for q in QUOTE_SUFFIXES:
            suffix = f"/{q}"
            if p.endswith(suffix):
                return p[: -len(suffix)]
        return base

    def is_supported(self, asset: str) -> bool:
        return asset.upper() in SUPPORTED_ASSETS

    def fetch_range_prices(self, pair: str, start_utc: datetime, end_utc: datetime) -> list[dict]:
        asset = self.asset_from_pair(pair)
        if not self.is_supported(asset):
            if self.debug:
                logging.info(f"[horus] skip unsupported asset {asset} for {pair}")
            return []

        params = {self.asset_key: asset, "format": "json"}
        if self.start_key:
            params[self.start_key] = int(start_utc.replace(tzinfo=timezone.utc).timestamp())
        if self.end_key:
            params[self.end_key] = int(end_utc.replace(tzinfo=timezone.utc).timestamp())
        if self.interval_key:
            params[self.interval_key] = self.interval_val

        r = requests.get(self.url, headers=self._headers(), params=params, timeout=10)
        if r.status_code in (400, 404, 422):
            if self.debug:
                logging.info(f"[horus] {pair}->{asset} http={r.status_code} url={r.url}")
            return []
        r.raise_for_status()
        raw = r.json()

        # Roostoo 有時可能回 dict（單一 ticker），統一轉成 list 處理
        if isinstance(raw, dict):
            raw = [raw]

        if self.debug and isinstance(raw, list) and raw:
            logging.info(
                f"[horus] {pair}->{asset} sample_keys={list(raw[0].keys())} n={len(raw)}"
            )

        out: list[dict] = []

        for row in (raw or []):
            ts_val = None
            for k in self.ts_keys:
                if k in row:
                    ts_val = row.get(k)
                    break

            px_val = None
            for k in self.px_keys:
                if k in row:
                    px_val = row.get(k)
                    break

            # 缺 timestamp 或 price 就丟掉
            if ts_val is None or px_val is None:
                continue

            # 🔴重點2：不要在這邊硬轉 timestamp，原樣丟給 main，讓 main 裡的 _to_iso8601_utc 處理
            try:
                price_f = float(px_val)
            except Exception:
                continue

            out.append({
                "timestamp": ts_val,   # 保留原始型態（int / float / str 都可以）
                "price": price_f
            })

        if self.debug:
            logging.info(f"[horus] {pair}->{asset} parsed_rows={len(out)}")

        return out
