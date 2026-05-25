import os

def sync_probability_table_to_supabase(local_table: dict):
    """Upload probability table to Supabase as a JSON blob."""
    try:
        from supabase import create_client
    except ImportError:
        return

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return

    try:
        client = create_client(url, key)
        client.table("bot_memory").upsert({
            "id": "ict_probabilities",
            "data": local_table
        }).execute()
    except Exception:
        pass


def load_probability_table_from_supabase() -> dict:
    """Load probability table from Supabase if local file is missing."""
    try:
        from supabase import create_client
    except ImportError:
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None

    try:
        client = create_client(url, key)
        res = client.table("bot_memory").select("data").eq("id", "ict_probabilities").execute()
        if res.data:
            return res.data[0]["data"]
    except Exception:
        pass
    return None