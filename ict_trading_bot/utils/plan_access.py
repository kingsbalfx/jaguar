"""Plan entitlements for signal delivery and MT5 mirror routing.

Bot-side mirror of ``jaguar-main/lib/pricing-config.js``. The website already
gates *email / in-app* signals by plan (``lib/signal-delivery.js``) but the MT5
mirror used to broadcast every bot trade to every account it could reach --
including accounts whose owner never bought bot/mirror access.

Rules encoded here:

* ``PLAN_ALIASES`` / ``PLAN_RANK``  -> the same canonical ids as the web app.
* ``PLAN_ENTITLEMENTS``            -> which plans include ``signals`` and
                                      ``mirrorTrading``.
* ``resolve_plan``                 -> pure resolver (subscription > role >
                                      bot_tier > free), mirrors
                                      ``resolvePlanFromSubscriptions``.
* ``resolve_user_plan``            -> Supabase lookup with cache + fail-open.

Environment switches (all optional):

    PLAN_ACCESS_ENABLED=true|false      kill switch (default true)
    MIRROR_ENFORCE_PLAN_TARGETS=true    enforce mirror plan targeting (default true)
    MIRROR_TARGET_PLANS=pro,lifetime    plans allowed to receive mirrored trades
    MIRROR_OWNER_LOGINS=1234567,...     logins that always bypass plan checks
    MIRROR_OWNER_EMAILS=you@mail.com    emails that always bypass plan checks
    MIRROR_OWNER_LOCAL_LOGIN=auto       is MT5_ACCOUNT_LOGIN an owner account?
                                        auto (default) = yes, except in a
                                        multi-account child, where it is the
                                        delegated account being traded
    MIRROR_PLAN_FAIL_OPEN=true|false    Supabase failure behaviour (default true)
    PLAN_LOOKUP_TTL=300                 plan cache TTL in seconds
    BOT_SIGNAL_TARGET_PLANS=premium,vip,pro,lifetime
                                        plans bot signals are delivered to
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan catalogue (keep in sync with jaguar-main/lib/pricing-config.js)
# ---------------------------------------------------------------------------
PLAN_ALIASES: Dict[str, str] = {
    "academy": "premium",
    "academy-student": "premium",
    "academy-students": "premium",
    "academy_student": "premium",
    "student": "premium",
    "students": "premium",
    "mentorship": "premium",
    "group-mentorship": "premium",
    "group_mentorship": "premium",
    "pro-mentorship": "pro",
    "pro_mentorship": "pro",
    "private-mentorship": "pro",
    "private_mentorship": "pro",
    "vip-desk": "vip",
    "vip_desk": "vip",
    "lifetime-academy": "lifetime",
    "lifetime_academy": "lifetime",
}

PLAN_RANK: Dict[str, int] = {
    "free": 0,
    "user": 0,
    "premium": 1,
    "academy": 1,
    "vip": 2,
    "pro": 3,
    "lifetime": 4,
    "admin": 99,
}

# Entitlements per canonical plan. ``mirrorTrading`` is the newer switch (added
# to the web pricing tiers at the same time as this module) and defaults to the
# plans whose features describe live execution / copy access.
PLAN_ENTITLEMENTS: Dict[str, Dict[str, Any]] = {
    "free": {"signals": True, "mirrorTrading": False, "maxSignalsPerDay": 1},
    "premium": {"signals": True, "mirrorTrading": False, "maxSignalsPerDay": 3},
    "vip": {"signals": True, "mirrorTrading": False, "maxSignalsPerDay": 8},
    "pro": {"signals": True, "mirrorTrading": True, "maxSignalsPerDay": 15},
    "lifetime": {"signals": True, "mirrorTrading": True, "maxSignalsPerDay": 5},
    "admin": {"signals": True, "mirrorTrading": True, "maxSignalsPerDay": 1000000},
}

DEFAULT_SIGNAL_PLANS: Sequence[str] = ("premium", "vip", "pro", "lifetime")
DEFAULT_MIRROR_PLANS: Sequence[str] = ("pro", "lifetime")

# Sentinel returned when a plan could not be resolved (Supabase unreachable, no
# owner identity, ...). Never a real plan id, so it can never match a target set.
UNKNOWN_PLAN = "unknown"

_WARNED: set = set()
_CACHE: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _truthy(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on", "y")


def _warn_once(key: str, message: str) -> None:
    if key in _WARNED:
        return
    _WARNED.add(key)
    logger.warning(message)


def _csv_env(name: str) -> List[str]:
    raw = _env(name)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _csv_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(item) for item in value]
    else:
        items = str(value).split(",")
    return [item.strip() for item in items if item and item.strip()]


# ---------------------------------------------------------------------------
# Pure plan helpers
# ---------------------------------------------------------------------------
def resolve_plan_id(value: Any) -> str:
    """Canonical plan id for anything an admin / web row may contain."""
    raw = str(value or "").strip().lower().replace(" ", "-")
    if not raw:
        return ""
    for candidate in (raw, raw.replace("_", "-"), raw.replace("-", "_")):
        if candidate in PLAN_ENTITLEMENTS:
            return candidate
        alias = PLAN_ALIASES.get(candidate)
        if alias:
            return alias
    return ""


def plan_rank(value: Any) -> int:
    canonical = resolve_plan_id(value)
    if canonical:
        return PLAN_RANK.get(canonical, 0)
    return PLAN_RANK.get(str(value or "").strip().lower(), 0)


def plan_features(value: Any) -> Dict[str, Any]:
    canonical = resolve_plan_id(value)
    if not canonical:
        return dict(PLAN_ENTITLEMENTS["free"])
    return dict(PLAN_ENTITLEMENTS.get(canonical, PLAN_ENTITLEMENTS["free"]))


def plan_allows_signals(value: Any) -> bool:
    return bool(plan_features(value).get("signals"))


def plan_allows_mirror(value: Any) -> bool:
    return bool(plan_features(value).get("mirrorTrading"))


def signal_target_plans() -> List[str]:
    """Plans the bot emails signals to (``BOT_SIGNAL_TARGET_PLANS``)."""
    requested = _csv_env("BOT_SIGNAL_TARGET_PLANS") or list(DEFAULT_SIGNAL_PLANS)
    resolved: List[str] = []
    for item in requested:
        plan = resolve_plan_id(item)
        if not plan:
            _warn_once(
                f"signal_plan:{item}",
                f"BOT_SIGNAL_TARGET_PLANS contains '{item}', which is not a known plan id.",
            )
            continue
        if plan not in resolved:
            resolved.append(plan)
    return resolved


def mirror_target_plans() -> List[str]:
    """Plans allowed to receive mirrored MT5 trades.

    Explicit ``MIRROR_TARGET_PLANS`` wins. Otherwise the signal plans are
    filtered down to the tiers that include mirror trading, and if that filter is
    empty (every signal plan is email-only) the documented default
    ``pro,lifetime`` is used.
    """
    explicit = _csv_env("MIRROR_TARGET_PLANS")
    candidates = explicit if explicit else list(signal_target_plans())
    resolved: List[str] = []
    for item in candidates:
        plan = resolve_plan_id(item)
        if not plan:
            if explicit:
                _warn_once(
                    f"mirror_plan:{item}",
                    f"MIRROR_TARGET_PLANS contains '{item}', which is not a known plan id.",
                )
            continue
        if explicit or plan_allows_mirror(plan):
            if plan not in resolved:
                resolved.append(plan)
    if not resolved:
        return list(DEFAULT_MIRROR_PLANS)
    return resolved


def enforcement_enabled() -> bool:
    """True when mirror peers must resolve to a mirror-target plan."""
    if not _truthy("PLAN_ACCESS_ENABLED", True):
        return False
    return _truthy("MIRROR_ENFORCE_PLAN_TARGETS", True)


def fail_open() -> bool:
    """Keep peers whose plan could not be resolved (default: yes)."""
    return _truthy("MIRROR_PLAN_FAIL_OPEN", True)


def _local_login_is_owner() -> bool:
    """Is ``MT5_ACCOUNT_LOGIN`` the operator's own account?

    ``auto`` (default) answers yes for a stand-alone / supervisor process (the
    machine trades the operator's own terminal) and no for a multi-account child:
    every child is spawned with ``MT5_ACCOUNT_LOGIN`` pointing at the *delegated*
    account it trades, which is usually a web-submitted account that must still be
    plan gated. Override with ``MIRROR_OWNER_LOCAL_LOGIN=always|never``.
    """
    mode = _env("MIRROR_OWNER_LOCAL_LOGIN", "auto").lower()
    if mode in ("always", "true", "1", "yes", "on"):
        return True
    if mode in ("never", "false", "0", "no", "off"):
        return False
    return not _truthy("MULTI_ACCOUNT_CHILD", False)


def _owner_logins() -> List[str]:
    logins = _csv_env("MIRROR_OWNER_LOGINS")
    for name in ("BOT_OWNER_LOGIN", "MT5_LOGIN"):
        value = _env(name)
        if value and value not in logins:
            logins.append(value)
    local_login = _env("MT5_ACCOUNT_LOGIN")
    if local_login and _local_login_is_owner() and local_login not in logins:
        logins.append(local_login)
    return logins


def _owner_emails() -> List[str]:
    emails = [item.lower() for item in _csv_env("MIRROR_OWNER_EMAILS")]
    for name in ("SUPER_ADMIN_EMAIL", "NEXT_PUBLIC_ADMIN_EMAIL", "BOT_OWNER_EMAIL"):
        value = _env(name).lower()
        if value and value not in emails:
            emails.append(value)
    return emails


def is_owner_account(
    login: Any = None, user_id: Any = None, email: Any = None
) -> bool:
    """True for the operator's own / admin accounts (never plan gated)."""
    login_str = str(login or "").strip()
    if login_str and login_str in _owner_logins():
        return True
    email_str = str(email or "").strip().lower()
    if email_str and email_str in _owner_emails():
        return True
    if not str(user_id or "").strip() and not email_str and not login_str:
        return True
    return False


# ---------------------------------------------------------------------------
# Subscription-based resolution (mirrors resolvePlanFromSubscriptions)
# ---------------------------------------------------------------------------
def _parse_iso(value: Any) -> Optional[float]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        from datetime import datetime, timezone

        text = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except Exception:
        return None


def subscription_active(subscription: Dict[str, Any], now: Optional[float] = None) -> bool:
    """Same rule as ``isSubscriptionActive`` in lib/subscription-status.js."""
    row = subscription or {}
    if str(row.get("status") or "").strip().lower() != "active":
        return False
    ended_at = _parse_iso(row.get("ended_at"))
    if ended_at is None:
        return True
    reference = time.time() if now is None else now
    return ended_at > reference


def resolve_plan(
    role: Any = "",
    bot_tier: Any = "",
    subscriptions: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Resolve the effective plan: subscription > role > bot_tier > free."""
    normalized_role = str(role or "user").strip().lower()
    if normalized_role in ("admin", "super_admin", "super-admin"):
        return {
            "plan": "admin",
            "rank": PLAN_RANK["admin"],
            "active": True,
            "source": "admin",
            "subscription": None,
            "expired": False,
        }

    role_plan = resolve_plan_id(normalized_role)
    tier_plan = resolve_plan_id(bot_tier)
    if role_plan and plan_rank(role_plan) > 0:
        fallback = {
            "plan": role_plan,
            "rank": plan_rank(role_plan),
            "active": True,
            "source": "profile_role",
            "subscription": None,
            "expired": False,
        }
    elif tier_plan and plan_rank(tier_plan) > 0:
        fallback = {
            "plan": tier_plan,
            "rank": plan_rank(tier_plan),
            "active": True,
            "source": "bot_tier",
            "subscription": None,
            "expired": False,
        }
    else:
        fallback = {
            "plan": "free",
            "rank": 0,
            "active": True,
            "source": "free",
            "subscription": None,
            "expired": False,
        }

    rows = [row for row in (subscriptions or []) if isinstance(row, dict)]
    active_rows = [row for row in rows if subscription_active(row)]
    active_rows.sort(key=lambda row: plan_rank(row.get("plan")), reverse=True)

    paid = None
    for row in active_rows:
        if plan_rank(row.get("plan")) > 0:
            paid = row
            break

    if paid is not None:
        paid_plan = resolve_plan_id(paid.get("plan"))
        if paid_plan and plan_rank(paid_plan) >= plan_rank(fallback["plan"]):
            return {
                "plan": paid_plan,
                "rank": plan_rank(paid_plan),
                "active": True,
                "source": "subscription",
                "subscription": paid,
                "expired": False,
            }

    lapsed = any(
        str(row.get("status") or "").strip().lower() == "active"
        and not subscription_active(row)
        for row in rows
    )
    resolved = dict(fallback)
    resolved["expired"] = lapsed
    return resolved


# ---------------------------------------------------------------------------
# Supabase lookups (cached)
# ---------------------------------------------------------------------------
def _cache_ttl() -> float:
    try:
        return max(0.0, float(_env("PLAN_LOOKUP_TTL", "300") or 300))
    except (TypeError, ValueError):
        return 300.0


def clear_cache() -> None:
    _CACHE.clear()


def _supabase_client():
    from config.supabase_credentials import (
        apply_supabase_env,
        resolve_supabase_credentials,
    )

    apply_supabase_env(quiet=True)
    resolved = resolve_supabase_credentials()
    url = resolved.get("url")
    key = resolved.get("service_key") or resolved.get("key")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL/SUPABASE_KEY are not configured")
    from supabase import create_client

    return create_client(url, key)


def _fetch_profile(client, user_id: str = "", email: str = "") -> Dict[str, Any]:
    """Load the profile row for a user id or email (best effort)."""
    columns = "id,email,role,bot_tier"
    for lookup in ("id", "email"):
        value = user_id if lookup == "id" else email
        if not value:
            continue
        query = client.table("profiles").select(columns)
        query = query.eq(lookup, value) if lookup == "id" else query.ilike(lookup, value)
        try:
            response = query.limit(1).execute()
        except Exception as exc:
            _warn_once(
                f"profile_lookup:{lookup}",
                f"plan_access: profiles lookup by {lookup} failed: {exc}",
            )
            continue
        rows = getattr(response, "data", None) or []
        if rows:
            return dict(rows[0])
    return {}


def _fetch_subscriptions(client, email: str = "") -> List[Dict[str, Any]]:
    if not email:
        return []
    try:
        response = (
            client.table("subscriptions")
            .select("email,plan,status,started_at,ended_at")
            .ilike("email", email)
            .execute()
        )
    except Exception as exc:
        _warn_once("subscriptions_lookup", f"plan_access: subscriptions lookup failed: {exc}")
        return []
    return [dict(row) for row in (getattr(response, "data", None) or []) if row]


def fetch_owner_plan(user_id: Any = None, email: Any = None) -> Dict[str, Any]:
    """Resolve the owner's plan from Supabase (never raises)."""
    user_id_str = str(user_id or "").strip()
    email_str = str(email or "").strip().lower()
    if not user_id_str and not email_str:
        # Nothing to look up: no owner identity was supplied.
        return {
            "plan": UNKNOWN_PLAN,
            "rank": 0,
            "active": False,
            "source": "no_identity",
            "subscription": None,
            "expired": False,
            "user_id": "",
            "email": "",
            "resolved_at": time.time(),
        }
    try:
        client = _supabase_client()
        profile = _fetch_profile(client, user_id_str, email_str)
        resolved_email = str(profile.get("email") or email_str).strip().lower()
        subscriptions = _fetch_subscriptions(client, resolved_email)
        result = resolve_plan(
            role=profile.get("role") or "",
            bot_tier=profile.get("bot_tier") or "",
            subscriptions=subscriptions,
        )
    except Exception as exc:
        _warn_once(f"plan_lookup:{user_id_str or email_str}", f"plan_access: {exc}")
        result = {
            "plan": UNKNOWN_PLAN,
            "rank": 0,
            "active": False,
            "source": "lookup_failed",
            "subscription": None,
            "expired": False,
            "error": str(exc),
        }
    result["user_id"] = user_id_str
    result["email"] = email_str
    result["resolved_at"] = time.time()
    return result


def resolve_user_plan(
    user_id: Any = None, email: Any = None, force: bool = False
) -> Dict[str, Any]:
    """Cached plan lookup. Returns ``plan='unknown'`` when Supabase is unavailable."""
    key = f"{str(user_id or '').strip().lower()}|{str(email or '').strip().lower()}"
    now = time.time()
    ttl = _cache_ttl()
    cached = _CACHE.get(key)
    if not force and cached and (now - float(cached.get("cached_at") or 0)) < ttl:
        return dict(cached)
    result = fetch_owner_plan(user_id=user_id, email=email)
    result["cached_at"] = now
    _CACHE[key] = dict(result)
    return result


# ---------------------------------------------------------------------------
# Decisions used by mirror trading / account supervision
# ---------------------------------------------------------------------------
def account_mirror_decision(
    login: Any = None, user_id: Any = None, email: Any = None
) -> Dict[str, Any]:
    """Decide whether an MT5 account may receive mirrored bot trades.

    Local accounts (no web owner) and owner/admin accounts are always allowed.
    Web-submitted accounts must resolve to a mirror-target plan; when the plan
    lookup itself fails the decision follows ``MIRROR_PLAN_FAIL_OPEN``.
    """
    login_str = str(login or "").strip()
    owner = is_owner_account(login=login_str, user_id=user_id, email=email)
    base = {
        "login": login_str,
        "user_id": str(user_id or "").strip(),
        "email": str(email or "").strip().lower(),
        "owner": owner,
        "enforced": enforcement_enabled(),
        "target_plans": mirror_target_plans(),
    }

    if owner:
        return {
            **base,
            "allowed": True,
            "plan": "owner",
            "plan_source": "owner",
            "mirror_entitled": True,
            "reason": "",
        }

    if not enforcement_enabled():
        return {
            **base,
            "allowed": True,
            "plan": "",
            "plan_source": "enforcement_off",
            "mirror_entitled": True,
            "reason": "",
        }

    if not str(user_id or "").strip() and not str(email or "").strip():
        # No web owner on record => a local / hand-managed account
        # (accounts_local.json, ACCOUNT_n_* env, owner's own terminal).
        # Those are never plan gated; only web-submitted accounts are.
        return {
            **base,
            "allowed": True,
            "plan": "",
            "plan_source": "local_account",
            "mirror_entitled": True,
            "reason": "",
        }

    resolved = resolve_user_plan(user_id=user_id, email=email)
    plan = str(resolved.get("plan") or "").strip().lower()
    lookup_failed = plan == UNKNOWN_PLAN or str(resolved.get("source")) == "lookup_failed"

    record = {
        **base,
        "plan": plan,
        "plan_source": str(resolved.get("source") or ""),
        "subscription_expired": bool(resolved.get("expired")),
        "mirror_entitled": plan_allows_mirror(plan),
    }

    if lookup_failed:
        if fail_open():
            return {**record, "allowed": True, "reason": "plan_lookup_failed_fail_open"}
        return {**record, "allowed": False, "reason": "plan_lookup_failed"}

    if plan == "admin":
        # Admin/super-admin accounts bypass plan targeting (same as the web app's
        # includeAdmin behaviour) - the operator must never gate themselves out.
        return {**record, "allowed": True, "reason": "", "owner": True, "mirror_entitled": True}

    if plan not in record["target_plans"]:
        return {**record, "allowed": False, "reason": "plan_not_targeted"}
    if not record["mirror_entitled"]:
        return {**record, "allowed": False, "reason": "plan_has_no_mirror_trading"}
    if not resolved.get("active"):
        return {**record, "allowed": False, "reason": "subscription_inactive"}
    return {**record, "allowed": True, "reason": ""}


def account_signal_decision(user_id: Any = None, email: Any = None) -> Dict[str, Any]:
    """Decide whether a subscriber's plan receives bot *signals* (email/in-app)."""
    resolved = resolve_user_plan(user_id=user_id, email=email)
    plan = str(resolved.get("plan") or "").strip().lower()
    targets = signal_target_plans()
    lookup_failed = plan == UNKNOWN_PLAN or str(resolved.get("source")) == "lookup_failed"
    if lookup_failed:
        allowed = fail_open()
        reason = "plan_lookup_failed_fail_open" if allowed else "plan_lookup_failed"
    elif plan == "admin":
        # Admin accounts receive everything, like the website's includeAdmin path.
        allowed, reason = True, ""
    elif plan not in targets:
        allowed, reason = False, "plan_not_targeted"
    elif not plan_allows_signals(plan):
        allowed, reason = False, "plan_has_no_signals"
    else:
        allowed, reason = True, ""
    return {
        "user_id": str(user_id or "").strip(),
        "email": str(email or "").strip().lower(),
        "plan": plan,
        "plan_source": resolved.get("source"),
        "allowed": allowed,
        "reason": reason,
        "target_plans": targets,
    }


def diagnostics() -> Dict[str, Any]:
    """Small snapshot for /admin endpoints and startup logging."""
    return {
        "enabled": _truthy("PLAN_ACCESS_ENABLED", True),
        "mirror_enforced": enforcement_enabled(),
        "mirror_target_plans": mirror_target_plans(),
        "signal_target_plans": signal_target_plans(),
        "owner_logins": _owner_logins(),
        "owner_emails": _owner_emails(),
        "local_login_owner": _local_login_is_owner(),
        "fail_open": fail_open(),
        "cache_ttl": _cache_ttl(),
        "cached_lookups": len(_CACHE),
    }
