#!/usr/bin/env python3
"""Single entry point for tracking PC component prices.

Usage:
    python track.py                     # scrape all + generate static data
    python track.py --server            # scrape all + start web server
    python track.py --scrape "RTX 5070" # test-scrape specific products only
    python track.py --scrape            # scrape all (same as default)
    python track.py --products my_list.json  # use a custom product list
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from price_tracker.scraper import load_products, filter_products, scrape_real_prices, PRODUCTS


def verify_data():
    """Check history.json and prices.json for anomalies, print summary with short_name."""
    import json
    docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data")
    prices_file = os.path.join(docs, "prices.json")
    history_file = os.path.join(docs, "history.json")

    if not os.path.exists(prices_file) or not os.path.exists(history_file):
        print("Run `python track.py` first to generate data files.")
        return

    with open(prices_file) as f:
        prices = json.load(f)
    with open(history_file) as f:
        history = json.load(f)

    print(f"Products in prices.json: {len(prices)}")
    print(f"Products in history.json: {len(history)}")

    msrp_map = {p["name"]: p.get("msrp", 0) for p in prices}
    sn_map = {p["name"]: p.get("short_name", p["name"]) for p in prices}

    # --- Match rates ---
    stores = ["原價屋 CoolPC", "欣亞 Sinya", "Autobuy", "Sunfar (isunfar.com.tw)"]
    total = len(prices) * len(stores)
    matched = 0
    for p in prices:
        for s in stores:
            if s in p.get("prices", {}):
                matched += 1
    print(f"Match rate: {matched}/{total} ({100*matched//total}%)")

    # --- Matched store titles (proof snippet) ---
    print("\n--- Matched store titles (latest scrape) ---")
    for p in prices:
        name = p["name"]
        sn = sn_map.get(name, name)
        for store, entry in p.get("prices", {}).items():
            title = entry.get("matched_title", "")
            if title:
                print(f"  [{sn:16s}] {store:16s} → {title}")
    print()

    # --- Anomaly: below-MSRP or extreme outliers ---
    anomalies = 0
    for p in prices:
        name = p["name"]
        msrp = msrp_map.get(name, 0)
        sn = sn_map.get(name, name)
        for store, entry in p.get("prices", {}).items():
            price = entry["price"]
            if msrp > 0 and price < msrp * 0.75:
                print(f"  ALERT [{sn}] {name} @ {store}: NT${price:,} < 75% of MSRP NT${msrp:,}")
                anomalies += 1

    # --- History outliers: single anomalous price surrounded by stable prices ---
    for prod_name, records in history.items():
        sn = sn_map.get(prod_name, prod_name)
        if len(records) < 3:
            continue
        sorted_recs = sorted(records, key=lambda r: r["recorded_at"])
        # group by store
        by_store = {}
        for r in sorted_recs:
            by_store.setdefault(r["store"], []).append(r)
        for store, recs in by_store.items():
            if len(recs) < 3:
                continue
            prices_list = [r["price"] for r in recs]
            # Check for single outliers: a price that differs from both neighbors by >20%
            for i in range(1, len(recs) - 1):
                p = prices_list[i]
                p_prev = prices_list[i-1]
                p_next = prices_list[i+1]
                if p_prev > 0 and p_next > 0:
                    if p < p_prev * 0.8 and p < p_next * 0.8:
                        print(f"  OUTLIER [{sn}] {prod_name} @ {store}: NT${p:,} at {recs[i]['recorded_at'][:19]} (prev NT${p_prev:,}, next NT${p_next:,})")
                        anomalies += 1

    if anomalies == 0:
        print("✓ No anomalies found")
    else:
        print(f"\nFound {anomalies} potential issue(s)")


def main():
    parser = argparse.ArgumentParser(description="PC component price tracker")
    parser.add_argument("--server", action="store_true", help="start web server after scraping")
    parser.add_argument("--scrape", nargs="*", default=None,
                        help="scrape specific products (by name substring); omit names to scrape all")
    parser.add_argument("--products", default=None,
                        help="path to products.json (default: products.json in project root)")
    parser.add_argument("--verify", action="store_true",
                        help="verify scraped data for anomalies")
    args = parser.parse_args()

    if args.verify:
        verify_data()
        return

    # 1. Load products (from file or inline)
    products = load_products(args.products)
    if args.scrape is not None:
        products = filter_products(products, args.scrape)

    print(f"Loaded {len(products)} product(s)")

    # 2. Scrape
    print("\n--- Scraping ---")
    results = scrape_real_prices(products)
    matched = sum(1 for store_prices in results.values() for v in store_prices.values())
    total = len(products) * 4  # 4 active stores
    print(f"\nMatched {matched}/{total} across stores\n")

    # 3. Print per-product summary
    print("--- Results ---")
    for prod in products:
        name = prod["name"]
        sn = prod.get("short_name", "")
        prices = []
        for store in ["原價屋 CoolPC", "欣亞 Sinya", "Autobuy", "Sunfar (isunfar.com.tw)"]:
            match = results.get(store, {}).get(name)
            if match:
                title = match.get("title", "")
                prices.append(f"{store}: NT${match['price']:,}")
                if title:
                    prices[-1] += f" [{title[:60]}]"
        tag = f" [{sn}]" if sn else ""
        if prices:
            print(f"  {name}{tag}: {', '.join(prices)}")
        else:
            print(f"  {name}{tag}: (no matches)")

    # 4. Generate static data (unless --scrape with specific products)
    if args.scrape is None or len(args.scrape) == 0:
        print("\n--- Generating static data ---")
        from scripts.generate_static import generate
        generate(products, results)
        print("Static data written to docs/")

    # 5. Start server if requested
    if args.server:
        print("\n--- Starting server ---")
        from server import start_server
        start_server()


if __name__ == "__main__":
    main()
