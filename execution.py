import logging
import time
import os
import csv
from datetime import datetime, timezone

import config

# 交易紀錄檔路徑，可從 config 覆寫
TRADE_LOG_FILE = getattr(config, "TRADE_LOG_FILE", "logs/trades.csv")


def _append_trade_log(order: dict, resp: dict):
    """
    把每筆下單（以及交易所回應 resp）寫到 CSV
    """
    try:
        os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)
        file_exists = os.path.exists(TRADE_LOG_FILE)
        with open(TRADE_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists:
                w.writerow(["ts", "symbol", "side", "qty", "resp"])
            w.writerow([
                datetime.now(timezone.utc).isoformat(),
                order.get("symbol"),
                order.get("side"),
                order.get("qty"),
                repr(resp),
            ])
    except Exception as e:
        logging.error(f"failed to append trade log: {e}")


def execute_orders(exchange_client, orders: list[dict], retry: int = 1):
    for o in orders:
        for attempt in range(retry + 1):
            try:
                # 注意：ExchangeClient.create_order 的參數叫 pair / quantity
                resp = exchange_client.create_order(
                    pair=o["symbol"],
                    side=o["side"],
                    quantity=o["qty"],
                    order_type="MARKET"
                )
                logging.info(f"ORDER OK: {o} -> {resp}")
                _append_trade_log(o, resp)
                break
            except Exception as e:
                logging.error(f"ORDER FAIL (try {attempt+1}): {o} -> {e}")
                time.sleep(1)
