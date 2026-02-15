import csv
from datetime import datetime

CSV_FILE = "fundamentals/news_calendar.csv"


def is_manual_news_block(currency: str) -> bool:
    today = datetime.utcnow().date()

    with open(CSV_FILE, newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            event_date = datetime.strptime(row["date"], "%Y-%m-%d").date()

            if event_date == today and row["currency"] == currency:
                return True

    return False
