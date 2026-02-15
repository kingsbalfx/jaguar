from backtest.metrics import calculate_metrics

def run_backtest(data, strategy):
    trades = []
    equity = 10000
    curve = []

    for candle in data:
        signal = strategy(candle)

        if signal:
            trades.append(signal)

        curve.append(equity)

    stats = calculate_metrics(trades, curve)
    return stats
