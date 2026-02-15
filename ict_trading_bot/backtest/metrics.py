import numpy as np

def calculate_metrics(trades, equity_curve):
    wins = [t for t in trades if t["result"] > 0]
    losses = [t for t in trades if t["result"] < 0]

    return {
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) if trades else 0,
        "profit_factor": abs(sum(t["result"] for t in wins) /
                              sum(t["result"] for t in losses)) if losses else 999,
        "max_drawdown": max_drawdown(equity_curve),
        "expectancy": np.mean([t["result"] for t in trades]) if trades else 0
    }


def max_drawdown(curve):
    peak = curve[0]
    dd = 0
    for x in curve:
        peak = max(peak, x)
        dd = min(dd, x - peak)
    return dd
