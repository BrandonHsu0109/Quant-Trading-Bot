# strategies/breakout_scalping.py
import math
import logging
from datetime import datetime, timezone, timedelta
from .base import Strategy
import config

# 內部狀態：紀錄每個幣是否在持倉、停損停利、逾時、冷卻
_open = {}        # pair -> {entry, sl, tp, t_expire, w}
_cooldown = {}    # pair -> datetime(utc) 冷卻結束時間

def _to_dt_utc(ts):
    """把 data_handler.buffers 裡的 timestamp 轉成 datetime(UTC)。"""
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, (int, float)):
        # 既支援秒也支援毫秒
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            if ts.endswith("Z"):
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
            if "+" in ts:
                return datetime.fromisoformat(ts).astimezone(timezone.utc)
            # 無時區就當作 UTC
            return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        except:
            return None
    return None

def _recent_window(dq, minutes: int):
    """回傳最近 N 分鐘的 (ts, px) 清單（已排序）"""
    if not dq:
        return []
    now_utc = _to_dt_utc(dq[-1][0])
    if not now_utc:
        return []
    cutoff = now_utc - timedelta(minutes=minutes)
    out = []
    for ts, px in dq:
        ts_dt = _to_dt_utc(ts)
        if ts_dt and ts_dt >= cutoff:
            out.append((ts_dt, float(px)))
    return out

def _post_cap(weights: dict[str, float], cap: float) -> dict[str, float]:
    if not weights:
        return {}
    w = {k: max(min(v, cap), -cap) for k, v in weights.items()}
    s = sum(abs(v) for v in w.values())
    if s <= 1e-9:
        return {}
    return w

class BreakoutScalping(Strategy):
    """
    觀念：
    - 觀察最近 lookback_min 的最高/最低。
    - 若現價往上突破 recent_high*(1+trig_eps) -> 做多（配重 w = alloc），
      停損/停利以「近窗區間 range=high-low」為基礎。
    - 逾時 timeout_min 後還沒 hit SL/TP 就平倉。
    - 出場後冷卻 cooldown_min 才能再次進場，避免連續假突破。
    - 僅做多（allow_short=False），簡單且穩定。
    """
    def __init__(self, allow_short: bool, params: dict | None = None):
        super().__init__("breakout_scalping", False, params or {})

    def target_weights(self, data_handler, prices, liquidity):
        desired = {}

        # 參數（可在 config.py 的 STRATEGIES 裡覆蓋）
        lookback_min   = int(self.params.get("lookback_min", 15))     # 觀察窗
        trig_eps       = float(self.params.get("trig_eps", 0.001))    # 突破觸發幅度（0.1%）
        sl_mult        = float(self.params.get("sl_mult", 0.5))       # 停損 = entry - sl_mult * range
        tp_mult        = float(self.params.get("tp_mult", 0.5))       # 停利 = entry + tp_mult * range
        timeout_min    = int(self.params.get("timeout_min", 10))      # 逾時強平
        cooldown_min   = int(self.params.get("cooldown_min", 5))      # 冷卻時間
        alloc          = float(self.params.get("trade_allocation_pct", 0.25))  # 單幣權重上限

        now_utc = datetime.now(timezone.utc)

        # 逐幣檢查
        for pair, dq in data_handler.buffers.items():
            # 流動性門檻（如需要）
            min_liq = float(self.params.get("min_liq", 0.0))
            if liquidity and liquidity.get(pair, 0.0) < min_liq:
                continue

            # 冷卻中就跳過
            cd_end = _cooldown.get(pair)
            if cd_end and now_utc < cd_end:
                continue

            # 取最近窗口
            win = _recent_window(dq, lookback_min)
            if len(win) < max(6, lookback_min // 2):  # 窗口裡資料太少就不做
                continue

            # 現價
            last_px = win[-1][1]
            # 最近窗的 high/low 與 range
            highs = [p for _, p in win]
            recent_high = max(highs)
            recent_low  = min(highs)
            r = max(recent_high - recent_low, 0.0)

            # 先處理已有倉位（更新停損停利/逾時）
            meta = _open.get(pair)
            if meta:
                # 出場條件：SL / TP / 逾時
                if last_px <= meta["sl"] or last_px >= meta["tp"] or now_utc >= meta["t_expire"]:
                    logging.info(f"[breakout_scalping] exit {pair} px={last_px:.6f} sl={meta['sl']:.6f} tp={meta['tp']:.6f}")
                    _open.pop(pair, None)
                    _cooldown[pair] = now_utc + timedelta(minutes=cooldown_min)
                else:
                    # 倉位維持 -> 配重
                    desired[pair] = abs(alloc)
                continue  # 有倉處理完就看下一個幣

            # 尚未在倉 -> 嘗試觸發入場（只做多）
            trigger_up = recent_high * (1.0 + trig_eps)
            if last_px >= trigger_up and r > 0:
                entry = last_px
                sl = entry - sl_mult * r
                tp = entry + tp_mult * r
                # 風險保護：確保 sl < entry < tp
                if sl >= entry or tp <= entry:
                    continue
                t_expire = now_utc + timedelta(minutes=timeout_min)
                _open[pair] = {
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "t_expire": t_expire,
                    "w": abs(alloc),
                }
                desired[pair] = abs(alloc)
                logging.info(f"[breakout_scalping] entry {pair} entry={entry:.6f} sl={sl:.6f} tp={tp:.6f} w={alloc:.3f}")

        # 只回傳持倉欲望（不在倉但沒觸發就 0 權重）
        return _post_cap(desired, cap=getattr(config, "MAX_POSITION_PER_SYMBOL", 0.35))

def build(allow_short: bool, params: dict | None = None):
    return BreakoutScalping(allow_short=False, params=params or {})
