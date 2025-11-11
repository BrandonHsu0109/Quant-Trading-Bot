# exchange_client.py
import time
import hmac
import hashlib
import requests
import logging
import config


def _now_ms() -> str:
    return str(int(time.time() * 1000))


def _sign_payload(payload: dict) -> tuple[dict, dict, str]:
    payload = dict(payload)
    payload["timestamp"] = _now_ms()

    sorted_keys = sorted(payload.keys())
    total_params = "&".join(f"{k}={payload[k]}" for k in sorted_keys)

    signature = hmac.new(
        config.SECRET_KEY.encode("utf-8"),
        total_params.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "RST-API-KEY": config.API_KEY,
        "MSG-SIGNATURE": signature,
    }
    return headers, payload, total_params


class ExchangeClient:
    def __init__(self):
        self.base_url = config.BASE_URL.rstrip("/")

    def get_exchange_info(self):
        url = f"{self.base_url}/v3/exchangeInfo"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()

    def get_all_tickers(self):
        url = f"{self.base_url}/v3/ticker"
        params = {"timestamp": _now_ms()}
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()

    def get_balance_raw(self):
        url = f"{self.base_url}/v3/balance"
        headers, payload, _ = _sign_payload({})
        resp = requests.get(url, headers=headers, params=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()

    def create_order(self, pair: str, side: str, quantity: float, order_type: str = "MARKET"):
        url = f"{self.base_url}/v3/place_order"
        payload = {
            "pair": pair,
            "quantity": quantity,
            "side": side.upper(),
            "type": order_type.upper(),
        }
        headers, payload_with_ts, _ = _sign_payload(payload)
        resp = requests.post(url, headers=headers, data=payload_with_ts, timeout=5)
        resp.raise_for_status()
        return resp.json()

    
    def get_positions_and_equity(self, prices: dict[str, float]):

        bal = self.get_balance_raw()
        logging.info("[exchange] raw balance response: %s", bal)

        if not bal.get("Success"):
            raise RuntimeError(f"balance failed: {bal}")

        wallet = bal.get("SpotWallet") or bal.get("Wallet") or {}

        positions: dict[str, float] = {}
        total_equity = 0.0
        usd_free = 0.0

        usd_info = wallet.get("USD") or wallet.get("USDT")
        if usd_info:
            usd_free = float(usd_info.get("Free", 0.0))
            total_equity += usd_free

        for coin, info in wallet.items():
            if coin in ("USD", "USDT"):
                continue
            free_amt = float(info.get("Free", 0.0))
            if free_amt <= 0:
                continue
            pair = f"{coin}/USD"
            positions[pair] = free_amt
            px = prices.get(pair, 0.0)
            total_equity += free_amt * px

        logging.info(
            "[exchange] parsed positions: %s, total_equity=%.2f, usd_free=%.2f",
            positions, total_equity, usd_free
        )
        return positions, total_equity, usd_free
