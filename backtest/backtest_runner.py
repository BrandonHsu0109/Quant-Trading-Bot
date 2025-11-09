import csv
from collections import defaultdict

import config
from data_handler import DataHandler
from strategy import generate_target_weights
from portfolio import calc_rebalance_orders


def load_csv(path: str):
    """
    假設 csv 長這樣：
    timestamp,symbol,price,volume24h
    2025-10-31T10:00:00Z,BTCUSDT,67890,123456
    ...
    """
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def run_backtest():
    rows = load_csv(config.BACKTEST_DATA_PATH)
    dh = DataHandler(lookback=config.LOOKBACK_MINUTES)

    # 假設一開始全是 USDT
    total_equity = config.TOTAL_CAPITAL_USDT
    positions = defaultdict(float)

    equity_curve = []

    current_ts = None
    current_tickers = []

    for r in rows:
        ts = r["timestamp"]
        if (current_ts is not None) and (ts != current_ts):
            # 到了下一分鐘，先跑一輪策略
            dh.update_from_tickers(current_tickers)

            momentum = dh.compute_momentum()
            prices = dh.get_latest_price_map()
            vols = dh.get_latest_volume24h_map()

            target_weights = generate_target_weights(momentum, vols)

            orders = calc_rebalance_orders(
                current_positions=positions,
                prices=prices,
                target_weights=target_weights,
                total_equity=total_equity,
                min_notional=1.0,
            )

            # 模擬成交（市場單直接吃）
            for o in orders:
                sym = o["symbol"]
                px = prices[sym]
                if o["side"] == "buy":
                    cost = o["qty"] * px
                    total_equity -= cost
                    positions[sym] += o["qty"]
                else:
                    gain = o["qty"] * px
                    total_equity += gain
                    positions[sym] -= o["qty"]

            # 記錄當前市值
            mkt_val = 0.0
            for sym, qty in positions.items():
                if sym in prices:
                    mkt_val += qty * prices[sym]
            equity = total_equity + mkt_val
            equity_curve.append((current_ts, equity))

            # reset
            current_tickers = []

        # 累積同一分鐘的 ticks
        current_ts = ts
        current_tickers.append({
            "symbol": r["symbol"],
            "price": r["price"],
            "volume24h": r["volume24h"],
        })

    # 最後一段也跑一次
    # ... 這裡你可以再補

    # 輸出結果
    for ts, eq in equity_curve[:20]:
        print(ts, eq)

if __name__ == "__main__":
    run_backtest()