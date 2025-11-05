def calc_rebalance_orders(current_positions: dict[str, float],
                          prices: dict[str, float],
                          target_weights: dict[str, float],
                          total_equity: float,
                          min_notional: float = 5.0) -> list[dict]:

    orders: list[dict] = []

    to_clear = set(current_positions.keys()) - set(target_weights.keys())
    for s in to_clear:
        qty = current_positions.get(s, 0.0)
        if qty > 0:
            orders.append({"symbol": s, "side": "sell", "qty": qty})

    for s, w in target_weights.items():
        price = prices.get(s)
        if not price:
            continue
        target_val = w * total_equity
        cur_qty = current_positions.get(s, 0.0)
        cur_val = cur_qty * price
        diff_val = target_val - cur_val

        if abs(diff_val) < min_notional:
            continue

        side = "buy" if diff_val > 0 else "sell"
        qty = abs(diff_val) / price
        orders.append({
            "symbol": s,
            "side": side,
            "qty": round(qty, 6),
        })

    return orders