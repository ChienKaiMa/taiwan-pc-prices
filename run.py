import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from price_tracker import scraper
from price_tracker.database import DB


def main():
    print("=" * 55)
    print("  台灣電腦零件價格追蹤器")
    print("  Taiwan PC Parts Price Tracker")
    print("=" * 55)

    print("\n[1/4] Scraping real prices from stores...")
    try:
        real_prices = scraper.scrape_real_prices()
    except Exception as e:
        print(f"  Scraping failed: {e}")
        print("  Falling back to fully synthetic data.")
        real_prices = None

    print("\n[2/4] Seeding database with prices...")
    db = DB()
    db.open()
    scraper.seed_demo_data(db, real_prices=real_prices)
    db.close()

    print("[3/4] Starting web server...\n")
    from server import start_server
    start_server()


if __name__ == "__main__":
    main()
