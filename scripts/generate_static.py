#!/usr/bin/env python3
"""Run price scraper and output static JSON files + index.html to docs/
for GitHub Pages hosting."""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from price_tracker.database import DB
from price_tracker.scraper import load_products, scrape_real_prices, PRODUCTS, STORES

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
DATA_DIR = os.path.join(DOCS_DIR, "data")
TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "web", "templates", "index.html")


def generate(products=None, pre_scraped=None):
    """Scrape prices, record to DB, and write static JSON + index.html.

    Args:
        products: list of product dicts (default: load_products())
        pre_scraped: optional pre-scraped results dict — skips scraping if given
    """
    if products is None:
        products = load_products()

    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. Run the scraper (or use pre-scraped results)
    if pre_scraped is not None:
        real = pre_scraped
        print("Using pre-scraped results")
    else:
        print("Running price scraper...")
        real = scrape_real_prices(products)

    # 2. Record snapshots to DB
    print("Recording snapshots...")
    db = DB()
    db.open()
    db.init_db()

    now = datetime.now()
    for prod in products:
        pid = db.upsert_product(prod["name"], prod["category"], prod.get("brand", ""), prod.get("spec", ""), msrp=prod.get("base_price", 0), short_name=prod.get("short_name", ""))
        for store in STORES:
            match = real.get(store["name"], {}).get(prod["name"])
            if match is None:
                continue
            price = match["price"]
            title = match.get("title", "")
            sid = db.upsert_store(store["name"], store.get("url", ""))
            db.record_price(pid, sid, price, now.isoformat(), title)
    db.commit()

    # 3. Generate prices.json (same format as /api/prices) — merge with existing
    print("Generating prices.json...")
    latest = db.get_latest_by_product()
    product_order = {p["name"]: i for i, p in enumerate(products)}
    latest.sort(key=lambda p: product_order.get(p["name"], 9999))
    prices_path = os.path.join(DATA_DIR, "prices.json")
    if os.path.exists(prices_path):
        try:
            with open(prices_path) as f:
                existing = json.load(f)
            merged = {p["name"]: p for p in latest}
            for old_p in existing:
                name = old_p["name"]
                if name not in merged:
                    merged[name] = old_p
                    continue
                for store, entry in old_p.get("prices", {}).items():
                    if store not in merged[name].get("prices", {}):
                        merged[name].setdefault("prices", {})[store] = entry
            latest = list(merged.values())
            latest.sort(key=lambda p: product_order.get(p["name"], 9999))
            msrp_map = {p["name"]: p.get("base_price", 0) for p in products}
            for p in latest:
                p["msrp"] = msrp_map.get(p["name"], p.get("msrp", 0))
            print(f"Merged with existing prices")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: could not merge existing prices: {e}")
    with open(prices_path, "w") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    # 4. Generate history.json — merge with existing, keep last 45 days
    print("Generating history.json...")
    history_path = os.path.join(DATA_DIR, "history.json")

    db_products = db.get_all_products()
    new_history = {}
    for p in db_products:
        h = db.get_price_history(p["name"], 45)
        if h:
            new_history[p["name"]] = h

    if os.path.exists(history_path):
        try:
            with open(history_path) as f:
                existing = json.load(f)
            for prod, records in existing.items():
                if prod not in new_history:
                    new_history[prod] = records
                else:
                    seen = {(r["store"], r["recorded_at"]) for r in new_history[prod]}
                    for r in records:
                        key = (r["store"], r["recorded_at"])
                        if key not in seen:
                            new_history[prod].append(r)
                            seen.add(key)
                    new_history[prod].sort(key=lambda x: x["recorded_at"])
            product_order = {p["name"]: i for i, p in enumerate(products)}
            new_history = dict(sorted(new_history.items(),
                                      key=lambda kv: product_order.get(kv[0], 9999)))
            print(f"Merged with existing history")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: could not merge existing history: {e}")

    with open(history_path, "w") as f:
        json.dump(new_history, f, ensure_ascii=False, indent=2)

    # 5. Copy index.html to docs/
    print("Copying index.html...")
    shutil.copy2(TEMPLATE, os.path.join(DOCS_DIR, "index.html"))

    db.close()
    print(f"Done. Generated in {DATA_DIR}")


if __name__ == "__main__":
    generate()
