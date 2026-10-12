"""Guaranteed signal fan-out — the "every registered email is notified" layer.

The bot does not own the subscriber list (the website does), so it cannot email
directly.  What it *can* do — and what was previously missing — is verify that
the website actually fanned the signal out, and retry when it did not.

The old ``_deliver_signal_to_website`` treated *any* ``2xx`` response as success
and returned ``accepted: True`` even when the website reported ``emailed=0`` /
``notified=0`` (this is the "missing email broadcasts" symptom: nothing was
queued for retry, subscribers got nothing).  :func:`dispatch` closes that hole:

1. the transport is called;
2. the response is **verified** against ``min_recipients`` and, optionally,
   against the exact target-plan audience the bot asked for;
3. only a *verified* delivery is reported as success;
4. an unverified/rejected delivery is persisted to Supabase, queued in the
   durable outbox for retry on the next scan, and raised to the ops log.

Environment
-----------
``BOT_SIGNAL_MIN_RECIPIENTS``   Minimum ``emailed``+``notified`` before a
                                delivery counts as successful (default 1).
``BOT_SIGNAL_STRICT_PLANS``     ``true`` also fails delivery when the website
                                reports an audience for fewer plans than the bot
                                targeted (default ``false``).
``BOT_SIGNAL_VERIFY_ACK``       ``false`` disables recipient verification and
                                restores the legacy "2xx == delivered" behaviour
                                (default ``true``).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Mapping, Optional

LOGGER = logging.getLogger("signal.dispatch")


def _truthy(name: str, default: str) -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(str(os.getenv(name, default)).strip()))
    except (TypeError, ValueError):
        return default


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def verify(delivery: Mapping[str, Any], expected_plans: Optional[List[str]] = None) -> Dict[str, Any]:
    """Inspect a transport result and decide whether it really reached users.

    Returns a dict with:
      * ``delivered``  — bool, True only when verified;
      * ``emailed``    — int recipients emailed (0 when unknown);
      * ``notified``   — int in-app notifications;
      * ``missing_plans`` — targeted plans the website reported no audience for;
      * ``reason``     — short machine-readable explanation when not delivered.
    """
    if not _truthy("BOT_SIGNAL_VERIFY_ACK", "true"):
        ok = bool(delivery.get("accepted"))
        return {
            "delivered": ok,
            "emailed": _as_int(delivery.get("emailed")),
            "notified": _as_int(delivery.get("notified")),
            "missing_plans": [],
            "reason": None if ok else (delivery.get("reason") or "rejected"),
        }

    if not delivery.get("accepted"):
        return {
            "delivered": False,
            "emailed": 0,
            "notified": 0,
            "missing_plans": list(expected_plans or []),
            "reason": delivery.get("reason") or "rejected",
        }

    response = delivery.get("response") or {}
    emailed = _as_int(response.get("emailed"))
    notified = _as_int(response.get("notified"))
    min_recipients = _env_int("BOT_SIGNAL_MIN_RECIPIENTS", 1)

    audience_by_plan = response.get("audienceByPlan")
    missing_plans: List[str] = []
    if expected_plans and isinstance(audience_by_plan, Mapping):
        for plan in expected_plans:
            if plan not in audience_by_plan:
                missing_plans.append(plan)

    if emailed + notified < min_recipients:
        return {
            "delivered": False,
            "emailed": emailed,
            "notified": notified,
            "missing_plans": missing_plans,
            "reason": "zero_recipients",
        }

    if missing_plans and _truthy("BOT_SIGNAL_STRICT_PLANS", "false"):
        return {
            "delivered": False,
            "emailed": emailed,
            "notified": notified,
            "missing_plans": missing_plans,
            "reason": "missing_plan_audience",
        }

    return {
        "delivered": True,
        "emailed": emailed,
        "notified": notified,
        "missing_plans": missing_plans,
        "reason": None,
    }


def dispatch(
    payload: Mapping[str, Any],
    *,
    transport: Callable[[Mapping[str, Any]], Dict[str, Any]],
    expected_plans: Optional[List[str]] = None,
    enqueue: Optional[Callable[[Mapping[str, Any], str], Any]] = None,
    persist: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    notify: Optional[Callable[[str, str, Mapping[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """Send ``payload`` and guarantee a retry when users were not reached.

    ``transport``     — the existing ``_deliver_signal_to_website`` sender.
    ``expected_plans``— ``BOT_SIGNAL_TARGET_PLANS`` resolved through
                        ``utils.plan_access`` (so this stays the single source of
                        truth for the plan catalogue).
    ``enqueue``       — ``utils.signal_outbox.enqueue``; called on failure.
    ``persist``       — ``persist_signal_to_supabase``; called on failure.
    ``notify``        — ``bot_log``; called on failure/zero-recipient.

    Returns ``{"delivered", "accepted", "verified", "emailed", "notified",
    "missing_plans", "reason", "response"}``.
    """
    result: Dict[str, Any] = {
        "delivered": False,
        "accepted": False,
        "verified": False,
        "emailed": 0,
        "notified": 0,
        "missing_plans": [],
        "reason": "transport_not_called",
        "response": {},
    }

    try:
        delivery = transport(payload) or {}
    except Exception as exc:  # never let a delivery error break the trade path
        LOGGER.error("signal dispatch transport raised: %s", exc, exc_info=True)
        delivery = {"accepted": False, "fallback_allowed": True, "reason": f"transport_exception:{exc}"}

    result["accepted"] = bool(delivery.get("accepted"))
    result["response"] = delivery.get("response") or {}

    verdict = verify(delivery, expected_plans)
    result.update(
        delivered=bool(verdict["delivered"]),
        verified=bool(verdict["delivered"]),
        emailed=int(verdict["emailed"]),
        notified=int(verdict["notified"]),
        missing_plans=list(verdict["missing_plans"]),
        reason=None if verdict["delivered"] else verdict["reason"],
    )

    if result["delivered"]:
        if result["emailed"] <= 0 and result["notified"] > 0:
            LOGGER.warning(
                "signal %s %s delivered in-app only (emailed=0, notified=%s)",
                payload.get("symbol"), payload.get("direction"), result["notified"],
            )
        return result

    # --- unverified / rejected: guarantee a retry ---------------------------
    reason = result["reason"] or "delivery_unverified"
    LOGGER.error(
        "SIGNAL DELIVERY FAILED | symbol=%s direction=%s reason=%s accepted=%s emailed=%s notified=%s",
        payload.get("symbol"), payload.get("direction"), reason,
        result["accepted"], result["emailed"], result["notified"],
    )
    if persist is not None:
        try:
            persist(payload)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("signal dispatch persist failed: %s", exc)
    if enqueue is not None:
        try:
            enqueue(payload, reason)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("signal dispatch enqueue failed: %s", exc)
    if notify is not None:
        try:
            notify(
                "signal_delivery_unverified",
                "Website accepted the signal but no subscriber was emailed/notified; "
                "queued for retry.",
                {
                    "symbol": payload.get("symbol"),
                    "direction": payload.get("direction"),
                    "reason": reason,
                    "emailed": result["emailed"],
                    "notified": result["notified"],
                    "missing_plans": result["missing_plans"],
                },
            )
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("signal dispatch notify failed: %s", exc)
    return result


__all__ = ["dispatch", "verify"]
