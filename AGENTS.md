# Agent Learnings — Taiwan PC Price Tracker

Domain knowledge, gotchas, and architecture decisions for future agents.

## Product Definition

- **`products.json`** at project root is the user-editable source of truth. Minimal format: just `name` + `category`.  
  The inline `PRODUCTS` list in `scraper.py` provides defaults (brand, spec, search, base_price, short_name).

- **`short_name`** is a concise display identifier (e.g. `"RX 9070"`, `"5060 Ti 16G"`, `"990 Pro"`).  
  Included in `--verify` output as a `[short_name]` tag for readable cross-references.

- **`base_price`** = Taiwan official launch MSRP for CPUs/GPUs, reference price for RAM/SSD.  
  Verified against: Mobile01, CoolPC launch articles, XFastest, 4Gamers, Coolaler, 小唐電腦 blog, 歐飛先生 blog.

## Scraping

### Store APIs

| Store | Method | Notes |
|-------|--------|-------|
| CoolPC (原價屋) | `evaluate.php` scrape via `coolpc_fetch_from_evaluate()` | Category-based. ~279 GPU products. |
| Sinya (欣亞) | `www.sinya.com.tw/api/search/getdata/1?keyword=...` | Per-product search. Falls back from gateway.sinya.com.tw (returned 404 historically). |
| Autobuy | `POST /ajax_prod_cate_order_by_{cat}_0` | Category IDs: CPU=448, GPU=2067, RAM=2749, SSD=5541. |
| PChome 24h | ✗ Excluded | Cloudflare anti-bot, no public API. |

### Matcher (`_match_product_by_name`)

Returns `(price, matched_title)` tuple or `None`.

Scoring:
```
score = matches*10 - bundle_penalty - variant_penalty - vram_penalty + (100 if exact match)
```

- **`bundle_penalty`** (+50): Keywords like "搭機", "套裝", "主機", "送", "救贖", "福利" indicate bundle/pre-built.
- **`variant_penalty`** (+60 each): Tier suffixes mismatch — `{kf, xt, gre, xtx, super, ultra, lite, max, ti, ks}`.  
  `"plus"` was removed from this list (it's a marketing modifier, e.g. "VENTUS 2X PLUS OC", "270K Plus").
- **`vram_penalty`** (+80): VRAM mismatch (8GB vs 16GB). Only fires when both target and candidate have extractable VRAM.
- **Minimum score**: 15 for most products, 5 for single-keyword products (CPUs after stopword removal).

### matched_title

Stores the store's actual product listing name (e.g. `"華碩 TUF Gaming AMD Radeon RX 9070 16GB GDDR6 OC Edition"`).  
Truncated to 120 chars via `_truncate_title()` to keep DB size manageable.  
Provides proof that the matcher picked the correct product — visible in `--verify` output and `prices.json`.

## Data Flow

```
track.py ──► scrape_real_prices() ──► generate_static.py ──► docs/data/{prices,history}.json
                                    └─► server.py (live mode, --server flag)
```

- `data/prices.db` is the SQLite DB. **Must be deleted before regeneration** (`rm data/prices.db`).
- `generate_static.py` merges new data with existing JSON (preserves history across renames).
- History merge deduplicates by `(store, recorded_at)`.
- `product_order` dict sorts output by PRODUCTS insertion order (8GB before 16GB).

## Database Schema

- `products`: id, name, short_name, category, brand, spec, msrp
- `stores`: id, name, url
- `price_snapshots`: id, product_id, store_id, price, recorded_at, matched_title

## Verification (`python track.py --verify`)

- Counts products, match rate, and anomaly detection:
  - **ALERT**: Price < 75% of MSRP (expected for old-gen CPUs)
  - **OUTLIER**: Single-record price dip >20% from both neighbors in history
- Shows `matched_title` per store for each product as proof of correct matching.

## Known Gotchas & Pitfalls

- **P3 Plus vs P310**: Short keyword `"p3"` falsely matches inside `"p310"` via substring `in` check.  
  Replaced P3 Plus product with P310 entirely.
- **evaluate.php glitches**: CoolPC's product list can return wrong items during a scrape.  
  June 12 01:24/01:27 had systematic wrong RAM/GPU prices. June 16 12:46 had RX 9070 at $17,990 (should be ~$24k).  
  These are single-timestamp outliers — confirmed by neighbors at the same store being stable.
- **VRAM in titles**: Some store listings omit VRAM (e.g. "ZOTAC RTX 5060 Ti" without "8GB"/"16GB").  
  The VRAM penalty won't fire if the candidate title lacks a VRAM string.
- **Sinya 5060 Ti 8GB→16GB cross-match**: Before VRAM penalty was added, the 5060 Ti 16GB product matched the 8GB card at Sinya (NT$16,590 instead of NT$20,490).
- **June 11 data**: All removed (92 entries) — systematic suspicious prices from initial scraper testing.
- **`"pc"` word boundary**: Bundle/pre-built filtering must use `\bpc\b` regex to avoid `PCIe`/`PCle` false positives.
- **`seed_demo_data()`**: Dead code, never called. Generates synthetic historical prices around real anchors.

## RAM/SSD Base Prices

Based on pre-surge (before Oct 2025) reference prices from blog sources:

| Product | Base Price | Source |
|---------|-----------|--------|
| Kingston Fury Beast DDR5-5600 32GB | NT$2,500 | 歐飛先生 blog (Oct 2025) |
| Corsair Vengeance DDR5-6000 32GB | NT$3,599 | CoolPC Apr 2025 range ($2,990–$5,999) |
| G.Skill Trident Z5 DDR5-6400 32GB | NT$3,688 | CoolPC Sep 2023 promo |
| WD SN850X 1TB | NT$3,950 | 小唐電腦 Dec 2025 |
| Kingston KC3000 1TB | NT$3,750 | 小唐電腦 Dec 2025 |
| Samsung 990 Pro 1TB | NT$4,999 | CoolPC reference (tentative) |
| Micron Crucial T500 1TB | NT$4,199 | CoolPC reference (tentative) |
| Micron Crucial P310 1TB | NT$3,999 | Estimated pre-surge (no direct source) |

DDR5 prices surged starting **October 2025** per 歐飛先生 timeline.

## Frontend

- `web/templates/index.html` → copied to `docs/index.html` by `generate_static.py`.
- `docs/index.html` is the GitHub Pages entry point (synced manually or via CI).
- **GitHub Buttons widget**: Source → Star (count) → Issue (count) order.
- **Two info-boxes**: Pricing mechanism + base-price evidence (both collapsible via `toggleInfo(el)`).
- **Header actions margin**: `.header-actions { margin-top: 1.2rem }`.
- **Cache busting**: Both refresh button and initial load pass `?_=timestamp` to `/api/prices` and `/api/history`.
- **Volatility cards**: Per-store time-based fluctuation. Amber "價格偏高" when avg > MSRP by >20%.
- **Historical low**: Falls back to current low if no history exists.
- **Favicon**: Inline SVG data URI with 🖥️ emoji.
