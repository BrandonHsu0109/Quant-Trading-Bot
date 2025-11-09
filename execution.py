import logging
import time

def execute_orders(exchange_client, orders: list[dict], retry: int = 1):
    """
    orders 格式：
    {
        "symbol": "BTC/USD",
        "side": "buy" 或 "sell",
        "qty": 0.123456,
    }
    """
    for o in orders:
        for attempt in range(retry + 1):
            try:
                resp = exchange_client.create_order(
                    pair=o["symbol"],        # ExchangeClient 的參數叫 pair
                    side=o["side"],          # "buy" / "sell"
                    quantity=o["qty"],       # ExchangeClient 的參數叫 quantity
                    order_type="MARKET",
                )
                logging.info(f"ORDER OK: {o} -> {resp}")
                break
            except Exception as e:
                logging.error(f"ORDER FAIL (try {attempt+1}): {o} -> {e}")
                time.sleep(1)
