import csv
from datetime import datetime
from pathlib import Path

CSV_FILE = Path(__file__).with_name("news_calendar.csv")


def is_manual_news_block(currency: str) -> bool:
    today = datetime.utcnow().date()
    target_currency = str(currency or "").strip().upper()

    if not target_currency or not CSV_FILE.exists():
        return False

    with open(CSV_FILE, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                event_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            except Exception:
                continue

            if event_date == today and str(row.get("currency") or "").strip().upper() == target_currency:
                return True

    return False
