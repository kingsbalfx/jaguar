"""Architecture smoke test for strict binary entry behavior."""

from strategy.strict_entry_validator import validate_strict_entry


FLAGS = {
    "external_liquidity": True,
    "liquidity_sweep": True,
    "displacement": True,
    "bos": True,
    "fvg": True,
    "order_block_confirmed": True,
    "premium_discount": True,
    "target_liquidity": True,
    "retracement": True,
    "lower_timeframe_confirmation": True,
}


perfect = validate_strict_entry(analysis={"context_alignment": "aligned"}, confirmation_flags=FLAGS)
assert perfect["passed"] and perfect["execution_route"] == "market"

for name in FLAGS:
    result = validate_strict_entry(
        analysis={"context_alignment": "aligned"},
        confirmation_flags={**FLAGS, name: False},
    )
    assert not result["passed"], name
    assert result["execution_route"] == "reject", name

conflict = validate_strict_entry(analysis={"context_alignment": "opposed"}, confirmation_flags=FLAGS)
assert not conflict["passed"]
assert conflict["failed_step"] == "narrative"
print("PASS: strict binary architecture")
