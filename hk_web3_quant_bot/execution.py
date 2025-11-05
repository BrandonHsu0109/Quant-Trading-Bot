import logging
import time

def execute_orders(exchange_client, orders: list[dict], retry: int = 1):
    for o in orders:
        for attempt in range(retry + 1):
            try:
                resp = exchange_client.create_order(
                    symbol=o["symbol"],
                    side=o["side"],
                    qty=o["qty"],
                    order_type="market"
                )
                logging.info(f"ORDER OK: {o} -> {resp}")
                break
            except Exception as e:
                logging.error(f"ORDER FAIL (try {attempt+1}): {o} -> {e}")
                time.sleep(1)