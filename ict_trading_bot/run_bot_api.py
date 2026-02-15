from bot_api import run_api

if __name__ == '__main__':
    # Bind to all interfaces for production-ready access
    run_api(host='0.0.0.0', port=8000)
