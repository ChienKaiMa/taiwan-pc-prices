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
from price_tracker.scraper import scrape_real_prices, PRODUCTS, STORES

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
DATA_DIR = os.path.join(DOCS_DIR, "data")
TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "web", "templates", "index.html")

os.makedirs(DATA_DIR, exist_ok=True)

# 1. Run the scraper
print("Running price scraper...")
real = scrape_real_prices()

# 2. Record snapshots to DB
print("Recording snapshots...")
db = DB()
db.open()
db.init_db()

now = datetime.now()
for prod in PRODUCTS:
    pid = db.upsert_product(prod["name"], prod["category"], prod.get("brand", ""), prod.get("spec", ""), msrp=prod.get("base_price", 0))
    for store in STORES:
        real_price = real.get(store["name"], {}).get(prod["name"])
        if real_price is None:
            continue
        sid = db.upsert_store(store["name"], store.get("url", ""))
        db.record_price(pid, sid, real_price, now.isoformat(), 0)
db.commit()

# 3. Generate prices.json (same format as /api/prices)
print("Generating prices.json...")
latest = db.get_latest_by_product()
with open(os.path.join(DATA_DIR, "prices.json"), "w") as f:
    json.dump(latest, f, ensure_ascii=False, indent=2)

# 4. Generate history.json (all products, last 45 days)
print("Generating history.json...")
products = db.get_all_products()
all_history = {}
for p in products:
    h = db.get_price_history(p["name"], 45)
    if h:
        all_history[p["name"]] = h
with open(os.path.join(DATA_DIR, "history.json"), "w") as f:
    json.dump(all_history, f, ensure_ascii=False, indent=2)

# 5. Copy index.html to docs/
print("Copying index.html...")
shutil.copy2(TEMPLATE, os.path.join(DOCS_DIR, "index.html"))

db.close()
print(f"Done. Generated in {DATA_DIR}")
