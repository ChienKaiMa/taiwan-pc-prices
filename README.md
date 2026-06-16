# Taiwan PC Component Price Tracker

Scrapes real prices from Taiwan PC stores (CoolPC, Sinya, Autobuy) and serves a live dashboard with automatic price updates.

## Quick Start

```bash
# 1. Clone and install
git clone <your-repo>
pip install requests

# 2. Edit product list (just name + category)
vim products.json

# 3. Scrape all prices and generate static dashboard
python track.py

# Or test-scrape specific products:
python track.py --scrape "RTX 5070"

# Verify matches and check for anomalies:
python track.py --verify

# Start web server with live dashboard:
python track.py --server
```

## `products.json` Format

```json
[
  {"name": "NVIDIA RTX 5070", "category": "GPU"},
  {"name": "Intel Core Ultra 5 245K", "category": "CPU"}
]
```

Only `name` and `category` are required. The scraper fills in brand, spec, search keywords, and base_price from built-in defaults. Categories: `CPU`, `GPU`, `RAM`, `SSD`.

## Automated Price Updates

The GitHub Action runs every 6 hours. Prices update ~4x daily with random jitter. Results publish to GitHub Pages.

## Stores Tracked

| Store | Status |
|---|---|
| 原價屋 CoolPC | ✓ (100% match rate) |
| 欣亞 Sinya | ✓ (83%) |
| Autobuy | ✓ (88%) |
| PChome 24h | ✗ (Cloudflare blocked) |

## Verification

```bash
python track.py --verify
```

Checks match rates, flags prices below 75% of MSRP (expected for old-gen CPUs), detects single-record price outliers from history, and shows the store's actual product name (`matched_title`) per product as proof of correct matching.

## Dashboard Features

- Per-store price columns (all 3 stores always shown)
- Volatility cards — per-category time-based price fluctuation
- 歷史低價 (historical low price) column
- 開始追蹤 (first tracked date) column
- Cache-busting refresh button
- Amber "價格偏高" for stable products >20% above MSRP

## Project Structure

```
├── products.json           # Your product list (edit this!)
├── track.py                # Single entry point
├── price_tracker/
│   ├── scraper.py          # Scrapers + matcher logic
│   └── database.py         # SQLite layer
├── scripts/
│   └── generate_static.py  # Generate static JSON + index.html
├── server.py               # Live API server + scheduler
├── web/templates/
│   └── index.html          # Dashboard template
└── docs/                   # GitHub Pages output
```
