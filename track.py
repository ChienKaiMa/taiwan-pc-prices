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


def main():
    parser = argparse.ArgumentParser(description="PC component price tracker")
    parser.add_argument("--server", action="store_true", help="start web server after scraping")
    parser.add_argument("--scrape", nargs="*", default=None,
                        help="scrape specific products (by name substring); omit names to scrape all")
    parser.add_argument("--products", default=None,
                        help="path to products.json (default: products.json in project root)")
    args = parser.parse_args()

    # 1. Load products (from file or inline)
    products = load_products(args.products)
    if args.scrape is not None:
        products = filter_products(products, args.scrape)

    print(f"Loaded {len(products)} product(s)")

    # 2. Scrape
    print("\n--- Scraping ---")
    results = scrape_real_prices(products)
    matched = sum(1 for store_prices in results.values() for v in store_prices.values())
    total = len(products) * 3  # 3 active stores
    print(f"\nMatched {matched}/{total} across stores\n")

    # 3. Print per-product summary
    print("--- Results ---")
    for prod in products:
        name = prod["name"]
        prices = []
        for store in ["原價屋 CoolPC", "欣亞 Sinya", "Autobuy"]:
            p = results.get(store, {}).get(name)
            if p:
                prices.append(f"{store}: NT${p:,}")
        if prices:
            print(f"  {name}: {', '.join(prices)}")
        else:
            print(f"  {name}: (no matches)")

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
