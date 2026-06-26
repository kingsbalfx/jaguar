import kingsbalfx_concept as kingsbalfx


class FakeMT5Connector:
    @staticmethod
    def calculate_volume_for_risk(symbol, entry, stop_loss, risk_amount):
        return 0.10 if symbol and entry > 0 and stop_loss > 0 and risk_amount > 0 else 0.0


def _candle(open_price, high, low, close, index):
    return {
        "open": float(open_price),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "volume": 1000.0 + index,
        "time": index,
    }


def _bullish_candles(count, start=100.0, step=1.0):
    candles = []
    price = start
    for index in range(count):
        open_price = price
        close = price + step * 0.65
        candles.append(_candle(open_price, close + step * 0.35, open_price - step * 0.20, close, index))
        price += step
    return candles


def _analysis_for_valid_buy():
    daily = _bullish_candles(18, start=100.0, step=1.8)
    daily[12] = _candle(126.0, 155.0, 125.0, 130.0, 12)
    daily[-2] = _candle(127.0, 132.0, 126.0, 131.5, 16)
    daily[-1] = _candle(131.0, 135.0, 130.5, 134.0, 17)

    h1 = _bullish_candles(40, start=120.0, step=0.45)
    h1[20] = _candle(142.0, 147.0, 141.5, 142.5, 20)
    h1[-4] = _candle(137.0, 137.5, 135.0, 135.6, 36)
    h1[-3] = _candle(135.5, 136.2, 134.8, 135.2, 37)
    h1[-2] = _candle(135.1, 137.2, 134.9, 136.9, 38)
    h1[-1] = _candle(136.8, 139.2, 136.5, 138.8, 39)

    m15 = _bullish_candles(30, start=130.0, step=0.32)
    m15[-4] = _candle(137.5, 138.0, 136.8, 137.1, 26)
    m15[-3] = _candle(137.0, 137.4, 136.4, 136.8, 27)
    m15[-2] = _candle(136.7, 137.8, 136.5, 137.6, 28)
    m15[-1] = _candle(137.5, 139.2, 137.4, 139.0, 29)

    m5 = _bullish_candles(20, start=134.0, step=0.25)
    m5[-5] = _candle(137.20, 137.45, 136.90, 137.30, 15)
    m5[-2] = _candle(138.00, 139.10, 137.95, 138.95, 18)
    m5[-1] = _candle(138.96, 140.25, 138.90, 140.05, 19)

    return {
        "DAILY": {"trend": "bullish", "recent_candles": daily},
        "HTF": {"trend": "bullish", "recent_candles": h1},
        "MTF": {"trend": "bullish", "recent_candles": m15},
        "LTF": {"trend": "bullish", "recent_candles": m5},
        "EXECUTION": {"trend": "bullish", "recent_candles": m5},
        "overall_trend": "bullish",
        "m5_candles": m5,
    }


def test_kingsbalfx_returns_valid_fallback_buy_request():
    result = kingsbalfx.evaluate(
        "TESTUSD",
        "buy",
        FakeMT5Connector,
        analysis=_analysis_for_valid_buy(),
        tick={"bid": 139.90, "ask": 140.00, "point": 0.01},
        account={"balance": 10000.0},
        risk_percent=1.0,
        minimum_rr=1.5,
    )

    assert result["valid"] is True
    request = result["request"]
    assert request["strategy"] == "kingsbalfx"
    assert request["direction"] == "buy"
    assert request["sl"] < request["entry"] < request["tp"]
    assert request["lot"] == 0.10


def test_kingsbalfx_rejects_unclear_h1_context():
    analysis = _analysis_for_valid_buy()
    analysis["HTF"]["trend"] = "range"
    analysis["HTF"]["recent_candles"] = [
        _candle(100.0, 101.0, 99.0, 100.2, index)
        for index in range(10)
    ]

    result = kingsbalfx.evaluate(
        "TESTUSD",
        None,
        FakeMT5Connector,
        analysis=analysis,
        tick={"bid": 100.0, "ask": 100.1, "point": 0.01},
        account={"balance": 10000.0},
    )

    assert result["valid"] is False
    assert result["reason"] == "h1_narrative_unclear"
