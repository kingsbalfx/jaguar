from ict_concepts.smt import detect_smt


def smt_confirmed(signal, correlated_data):
    """
    correlated_data example:
    EURUSD ↔ DXY
    BTC ↔ ETH
    NAS100 ↔ SP500
    """

    # if no correlated data provided, skip SMT check (allow)
    if not correlated_data or "main" not in correlated_data or "correlated" not in correlated_data:
        return True

    try:
        smt = detect_smt(
            correlated_data["main"],
            correlated_data["correlated"],
            expected_direction=signal.get("direction"),
            correlation_mode=correlated_data.get("correlation_mode", "positive"),
        )
    except Exception:
        return True

    if not isinstance(smt, dict):
        return True

    if not smt.get("confirmed"):
        return True

    return bool(smt.get("direction_aligned"))
