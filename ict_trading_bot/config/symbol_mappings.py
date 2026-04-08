# Broker symbol alternatives to try when a requested symbol is unavailable in MT5.

CRYPTO_ASSETS = [
    "BTC",
    "ETH",
    "DOGE",
    "BNB",
    "SOL",
    "XRP",
    "TRX",
    "TON",
    "ADA",
    "AVAX",
    "LTC",
    "BCH",
    "EOS",
    "MATIC",
    "LINK",
    "UNI",
]

CRYPTO_QUOTES = ["USD", "USDT", "USDC", "EUR", "GBP"]
BROKER_SUFFIXES = [
    "",
    "m",
    "M",
    ".m",
    ".M",
    ".i",
    "-i",
    ".r",
    ".raw",
    ".pro",
    ".ecn",
    ".std",
    ".micro",
    "#",
    "_",
]
CRYPTO_SEPARATORS = ["", "/", "-", "_", "."]
METAL_MAPPINGS = {
    "XAUUSD": ["XAUUSD", "XAU", "GOLD", "GOLDUSD", "XAU/USD"],
    "XAGUSD": ["XAGUSD", "XAG", "SILVER", "SILVERUSD", "XAG/USD"],
    "XPTUSD": ["XPTUSD", "XPT", "PLATINUM", "PLATINUMUSD", "XPT/USD"],
    "XPDUSD": ["XPDUSD", "XPD", "PALLADIUM", "PALLADIUMUSD", "XPD/USD"],
}


def _dedupe(items):
    out = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _crypto_candidates(asset):
    asset = str(asset or "").upper()
    candidates = [asset]

    for quote in CRYPTO_QUOTES:
        for separator in CRYPTO_SEPARATORS:
            pair = f"{asset}{separator}{quote}"
            candidates.append(pair)
            candidates.append(f"X{pair}")
            candidates.append(f"{pair}.IDEAL")
            for suffix in BROKER_SUFFIXES:
                candidates.append(f"{pair}{suffix}")

    if asset == "BTC":
        candidates.extend(["XBT", "XBTUSD", "XBTUSDT", "BTCUSD-IDEAL"])

    return _dedupe(candidates)


MAPPINGS = {}

for _asset in CRYPTO_ASSETS:
    MAPPINGS[_asset] = _crypto_candidates(_asset)
    MAPPINGS[f"{_asset}USD"] = _crypto_candidates(_asset)
    MAPPINGS[f"{_asset}USDT"] = _crypto_candidates(_asset)

for _canonical, _aliases in METAL_MAPPINGS.items():
    _metal_candidates = []
    for _alias in _aliases:
        _metal_candidates.append(_alias)
        for _suffix in BROKER_SUFFIXES:
            _metal_candidates.append(f"{_alias}{_suffix}")
    MAPPINGS[_canonical] = _dedupe(_metal_candidates)
    for _alias in _aliases:
        MAPPINGS[_alias] = MAPPINGS[_canonical]

MAPPINGS["DOGEUSD"] = _dedupe(["DOGUSD", *MAPPINGS["DOGEUSD"]])
MAPPINGS["ETHBTC"] = ["ETHBTC", "ETHBTC.i", "ETH/BTC", "ETH-BTC", "ETHBTCm", "ETHBTC.raw", "ETHUSD", "ETH"]


def _infer_crypto_asset(base):
    normalized = str(base or "").upper().replace("/", "").replace("-", "").replace("_", "").replace(".", "")
    variants = [normalized]
    if normalized in CRYPTO_ASSETS or normalized == "XBT":
        variants.append(normalized)
    else:
        for suffix in ("MICRO", "RAW", "PRO", "ECN", "STD", "M", "I", "R", "#"):
            if normalized.endswith(suffix) and len(normalized) > len(suffix):
                variants.append(normalized[: -len(suffix)])

    for variant in _dedupe(variants):
        if variant in CRYPTO_ASSETS:
            return variant
        if variant == "XBT":
            return "BTC"
        for quote in CRYPTO_QUOTES:
            if variant.endswith(quote) and len(variant) > len(quote):
                asset = variant[: -len(quote)]
                if asset in CRYPTO_ASSETS or asset == "XBT":
                    return "BTC" if asset == "XBT" else asset
    return None


def _metal_candidates(base):
    normalized = str(base or "").upper()
    if normalized in MAPPINGS and any(normalized in aliases for aliases in METAL_MAPPINGS.values()):
        return MAPPINGS[normalized]
    for canonical, aliases in METAL_MAPPINGS.items():
        if normalized == canonical or normalized in aliases:
            return MAPPINGS[canonical]
    return []


def candidates_for(symbol):
    raw = str(symbol or "").strip()
    base = raw.upper()
    mapped = MAPPINGS.get(base, [])
    asset = _infer_crypto_asset(base)

    generated = []
    if asset:
        generated.extend(_crypto_candidates(asset))
    elif _metal_candidates(base):
        generated.extend(_metal_candidates(base))
    else:
        base_variants = [base, f"X{base}"]
        if base.endswith("USD") and len(base) > 3:
            asset_part = base[:-3]
            base_variants.extend([asset_part, f"{asset_part}/USD", f"{asset_part}-USD", f"{asset_part}.USD"])
        for variant in base_variants:
            for suffix in BROKER_SUFFIXES:
                generated.append(f"{variant}{suffix}")

    return _dedupe([raw, base, *mapped, *generated])
