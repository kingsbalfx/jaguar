"""
Bot Logging System - Centralized logging to console and Supabase
"""

def bot_log(event, message, payload=None, persist=True):
    """
    Log a bot event to console and optionally to Supabase.
    
    Args:
        event: Event type/name (used for categorization)
        message: Human-readable message
        payload: Dict with additional context data
        persist: Whether to save to Supabase (requires append_log and persist_log_to_supabase)
    """
    entry = payload or {}
    print(f"[BOT] {message}")
    
    # Lazy import to avoid circular dependencies
    try:
        from bot_state import append_log
        append_log(event, message, entry)
    except (ImportError, Exception):
        pass  # Gracefully handle if bot_state not available
    
    if persist:
        try:
            from dashboard.bridge import persist_log_to_supabase
            persist_log_to_supabase(event, {"message": message, **entry})
        except (ImportError, Exception):
            pass  # Gracefully handle if Supabase is unavailable


def bot_log_simple(message):
    """
    Simple logging without event tracking or persistence.
    
    Args:
        message: Message to log
    """
    print(f"[BOT] {message}")
