from bot_api import run_api
from config.supabase_credentials import bootstrap as bootstrap_supabase
from dotenv import load_dotenv

if __name__ == '__main__':
    # Load .env, then publish validated Supabase credentials (env / .env / local
    # store) so the API-only mode can persist logs and coordinate mirror trades.
    load_dotenv()
    bootstrap_supabase()

    # Bind to all interfaces for production-ready access
    run_api(host='0.0.0.0', port=8000)
