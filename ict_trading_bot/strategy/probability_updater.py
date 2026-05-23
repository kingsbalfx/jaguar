"""
PROBABILITY UPDATER – Live learning from trade outcomes.
"""

import json
from pathlib import Path
from strategy.ict_setup_quality import PROBABILITY_FILE, _default_table

def update_probability_table(regime, features, win):
    path = PROBABILITY_FILE
    if path.exists():
        try:
            with open(path, 'r') as f:
                table = json.load(f)
        except:
            table = _default_table()
    else:
        table = _default_table()

    regime_table = table.setdefault(regime, {"default": 0.45, "count": 0})
    regime_table["count"] = regime_table.get("count", 0) + 1

    sweep = features.get("sweep", False)
    displacement = features.get("displacement", False)
    ob = features.get("ob_exists", False)
    if sweep and displacement and ob:
        key = "sweep_yes_displacement_yes_ob_yes"
    elif sweep and displacement and not ob:
        key = "sweep_yes_displacement_yes_ob_no"
    elif sweep and not displacement and ob:
        key = "sweep_yes_displacement_no_ob_yes"
    else:
        key = "default"

    sub = regime_table.get(key)
    if not isinstance(sub, dict):
        sub = {"wins": 0, "total": 0}
        regime_table[key] = sub
    sub["total"] = sub.get("total", 0) + 1
    if win:
        sub["wins"] = sub.get("wins", 0) + 1
    if sub["total"] > 0:
        sub["probability"] = round(sub["wins"] / sub["total"], 4)

    # Update default
    total_wins = sum(v.get("wins", 0) for v in regime_table.values() if isinstance(v, dict))
    total_trades = sum(v.get("total", 0) for v in regime_table.values() if isinstance(v, dict))
    if total_trades > 0:
        regime_table["default"] = round(total_wins / total_trades, 4)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(table, f, indent=2)