#base.py
class Strategy:
    def __init__(self, name: str, allow_short: bool, params: dict | None = None):
        self.name = name
        self.allow_short = bool(allow_short)
        self.params = params or {}

    def target_weights(self, data_handler, prices: dict[str, float], liquidity: dict[str, float]) -> dict[str, float]:
        raise NotImplementedError
