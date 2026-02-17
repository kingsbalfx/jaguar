try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

from utils.mt5_credentials import fetch_mt5_credentials

SYMBOLS_TO_CHECK = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "XAUUSD", "ETHBTC"]

if mt5 is None:
    raise SystemExit("MetaTrader5 is not available on this platform. Run on Windows with MT5 installed.")

print('Initializing MT5...')
creds = fetch_mt5_credentials()
try:
    login_value = int(creds.get("login"))
except Exception:
    login_value = creds.get("login")
init_ok = mt5.initialize(login=login_value, password=creds.get("password"), server=creds.get("server"))
print('initialize() ->', init_ok)

try:
    term_info = mt5.terminal_info()
    print('Terminal path:', term_info.path)
except Exception:
    print('Terminal info: unavailable')

acct = mt5.account_info()
if acct:
    print('Account login:', acct.login)
    print('Account server:', acct.server)
    print('Balance:', acct.balance)
else:
    print('Account info: NOT CONNECTED')

print('\nChecking symbol availability:')
for s in SYMBOLS_TO_CHECK:
    info = mt5.symbol_info(s)
    if info is None:
        print(f' - {s}: NOT AVAILABLE')
    else:
        print(f' - {s}: available, digits={info.digits}, trade_mode={getattr(info, "trade_mode", "N/A")}, tick_size={getattr(info, "tick_size", "N/A")}')

# Show first 20 symbols
print('\nListing first 20 symbols from MT5:')
symbols = mt5.symbols_get()
for i, si in enumerate(symbols[:20]):
    print(f' {i+1}.', si.name)

mt5.shutdown()
print('\nMT5 shutdown')
