import time
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import config
from exchange_client import ExchangeClient
from data_handler import DataHandler
from portfolio import calc_rebalance_orders
from execution import execute_orders
from logger_utils import setup_logging
from strategies.manager import StrategyManager

def main():
    setup_logging()
    logging.info("Starting Roostoo Quant Bot ...")
    client = ExchangeClient()
    dh = DataHandler(lookback=config.LOOKBACK_MINUTES)
    sm = StrategyManager(allow_short=config.ALLOW_SHORT)
    ny = ZoneInfo("America/New_York")
    last_ny_date = None
    while True:
        loop_start = time.time()
        try:
            tickers_resp = client.get_all_tickers()
            if not tickers_resp.get("Success", False):
                logging.warning(f"ticker api failed: {tickers_resp}")
                raise RuntimeError("ticker api failed")
            market_data = tickers_resp.get("Data", {})
            dh.update_from_roostoo(market_data)
            prices = dh.get_latest_price_map()
            liquidity = dh.get_latest_liquidity_map()
            target_weights = sm.combine(dh, prices, liquidity)
            if getattr(config, "DEBUG_LOG_WEIGHTS", False):
                if target_weights:
                    picks = sorted(target_weights.items(), key=lambda x: abs(x[1]), reverse=True)[:int(getattr(config,"DEBUG_TOP_N",5))]
                    logging.info("[dispatch] final picks: " + ", ".join(f"{k}:{v:+.3f}" for k,v in picks))
                else:
                    logging.info("[dispatch] no picks this round")
            positions, total_equity = client.get_positions_and_equity(prices)
            orders = calc_rebalance_orders(
                current_positions=positions,
                prices=prices,
                target_weights=target_weights,
                total_equity=total_equity,
                min_notional=getattr(config, "MIN_NOTIONAL", 1.0)
            )
            if orders:
                logging.info(f"Generated {len(orders)} orders.")
                execute_orders(client, orders, retry=1)
            else:
                logging.info("No orders this round.")
            ny_now = datetime.now(timezone.utc).astimezone(ny)
            if last_ny_date is None:
                last_ny_date = ny_now.date()
            if ny_now.date() != last_ny_date:
                last_ny_date = ny_now.date()
        except Exception as e:
            logging.exception(f"MAIN LOOP ERROR: {e}")
        elapsed = time.time() - loop_start
        sleep_sec = max(1, config.ORDER_INTERVAL_SEC - elapsed)
        time.sleep(sleep_sec)

if __name__ == "__main__":
    main()
