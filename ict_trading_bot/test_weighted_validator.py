"""Smoke test for the binary entry validator."""

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

result = validate_strict_entry(
    analysis={"context_alignment": "aligned"},
    confirmation_flags=FLAGS,
)
assert result["passed"]
assert result["execution_route"] == "market"
print(f"STRICT ENTRY: PASS | {result['reason']}")

failed = validate_strict_entry(
    analysis={"context_alignment": "aligned"},
    confirmation_flags={**FLAGS, "liquidity_sweep": False},
)
assert not failed["passed"]
assert failed["failed_step"] == "liquidity_sweep"
