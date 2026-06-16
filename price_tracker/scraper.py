import os
import random
import math
import re
import json
import time
from datetime import datetime, timedelta

import requests

# ── Store definitions ──────────────────────────────────────────────
# PChome 24h is excluded because it uses Cloudflare anti-bot protection
# and lacks a public API or category-page listing — scraping individual
# product pages at scale is not feasible.  All prices would be synthetic.
STORES = [
    {"name": "原價屋 CoolPC", "url": "https://www.coolpc.com.tw"},
    {"name": "欣亞 Sinya", "url": "https://www.sinya.com.tw"},
    {"name": "Autobuy", "url": "https://www.autobuy.tw"},
]

# ── Product list ──────────────────────────────────────────────────
# Each product may optionally have a "search" keyword used when querying
# per-store APIs (Sinya, CoolPC).  Autobuy is scraped by category page,
# so we map category → category_id below.
#
# You can either edit PRODUCTS directly below, or put your list in
# products.json at the project root (simpler — just name + category).
# Use `python track.py --products products.json` or create track.py
# which loads it automatically.
#
# Products can be a simple dict with just "name" and "category";
# the scraper fills in missing defaults (search=name, brand inferred
# from name, etc.).

PRODUCTS = [
    {"name": "Intel Core Ultra 5 245K",         "category": "CPU", "brand": "Intel",   "spec": "14C/14T 4.2-5.2GHz Arrow Lake",              "base_price": 10400, "search": "Ultra 5 245K", "short_name": "245K"},
    {"name": "Intel Core Ultra 7 265K",         "category": "CPU", "brand": "Intel",   "spec": "20C/20T 3.9-5.5GHz Arrow Lake",              "base_price": 13600, "search": "265K",        "short_name": "265K"},
    {"name": "Intel Core Ultra 7 270K Plus",    "category": "CPU", "brand": "Intel",   "spec": "24C/24T 3.7-5.5GHz Arrow Lake Refresh",      "base_price": 12500, "search": "270K",        "short_name": "270K"},
    {"name": "Intel Core Ultra 9 285K",         "category": "CPU", "brand": "Intel",   "spec": "24C/24T 3.7-5.7GHz Arrow Lake",              "base_price": 19800, "search": "285K",        "short_name": "285K"},
    {"name": "AMD Ryzen 7 7800X3D",            "category": "CPU", "brand": "AMD",     "spec": "8C/16T 4.2-5.0GHz 3D V-Cache",              "base_price": 14750, "search": "7800X3D",    "short_name": "7800X3D"},
    {"name": "AMD Ryzen 5 7500F",              "category": "CPU", "brand": "AMD",     "spec": "6C/12T 3.7-5.0GHz Zen 4",                   "base_price": 5250,  "search": "7500F",      "short_name": "7500F"},
    {"name": "AMD Ryzen 7 7700",               "category": "CPU", "brand": "AMD",     "spec": "8C/16T 3.8-5.3GHz Zen 4",                   "base_price": 10400, "search": "7700",       "short_name": "7700"},
    {"name": "NVIDIA RTX 5060",                "category": "GPU", "brand": "NVIDIA",  "spec": "8GB GDDR7",                                  "base_price": 10990, "search": "RTX 5060",   "short_name": "RTX 5060"},
    {"name": "NVIDIA RTX 5060 Ti 8GB",         "category": "GPU", "brand": "NVIDIA",  "spec": "8GB GDDR7",                                  "base_price": 12190, "search": "5060 Ti",   "short_name": "5060 Ti 8G"},
    {"name": "NVIDIA RTX 5060 Ti 16GB",        "category": "GPU", "brand": "NVIDIA",  "spec": "16GB GDDR7",                                 "base_price": 13790, "search": "5060 Ti",   "short_name": "5060 Ti 16G"},
    {"name": "NVIDIA RTX 5070",                "category": "GPU", "brand": "NVIDIA",  "spec": "12GB GDDR7",                                 "base_price": 19990, "search": "RTX 5070",   "short_name": "RTX 5070"},
    {"name": "NVIDIA RTX 5070 Ti",             "category": "GPU", "brand": "NVIDIA",  "spec": "16GB GDDR7",                                 "base_price": 26990, "search": "RTX 5070 Ti", "short_name": "5070 Ti"},
    {"name": "NVIDIA RTX 5080",                "category": "GPU", "brand": "NVIDIA",  "spec": "16GB GDDR7",                                 "base_price": 35990, "search": "RTX 5080",   "short_name": "RTX 5080"},
    {"name": "NVIDIA RTX 5090",                "category": "GPU", "brand": "NVIDIA",  "spec": "32GB GDDR7",                                 "base_price": 71990, "search": "5090",       "short_name": "5090"},
    {"name": "AMD RX 9070",                    "category": "GPU", "brand": "AMD",     "spec": "16GB GDDR6",                                 "base_price": 19990, "search": "RX 9070",   "short_name": "RX 9070"},
    {"name": "AMD RX 9070 XT",                 "category": "GPU", "brand": "AMD",     "spec": "16GB GDDR6",                                 "base_price": 22990, "search": "RX 9070 XT", "short_name": "9070 XT"},
    {"name": "AMD RX 9060 XT 8GB",           "category": "GPU", "brand": "AMD",     "spec": "8GB GDDR6",                                  "base_price": 10490, "search": "9060 XT",   "short_name": "9060 XT 8G"},
    {"name": "AMD RX 9060 XT 16GB",          "category": "GPU", "brand": "AMD",     "spec": "16GB GDDR6",                                 "base_price": 12490, "search": "9060 XT",   "short_name": "9060 XT 16G"},
    {"name": "Corsair Vengeance DDR5-6000 32GB",   "category": "RAM", "brand": "Corsair", "spec": "32GB (2x16GB) DDR5-6000 CL30",       "base_price": 3599, "search": "Vengeance DDR5-6000", "short_name": "Vengeance 6000"},
    {"name": "G.Skill Trident Z5 DDR5-6400 32GB",  "category": "RAM", "brand": "G.Skill",  "spec": "32GB (2x16GB) DDR5-6400 CL32",       "base_price": 3688, "search": "Trident Z5 DDR5-6400", "short_name": "Trident Z5 6400"},
    {"name": "Kingston Fury Beast DDR5-5600 32GB", "category": "RAM", "brand": "Kingston", "spec": "32GB (2x16GB) DDR5-5600 CL36",       "base_price": 2500, "search": "Fury Beast",  "short_name": "Fury Beast 5600"},
    {"name": "Samsung 990 Pro 1TB",            "category": "SSD", "brand": "Samsung",  "spec": "1TB NVMe M.2 PCIe 4.0", "base_price": 4999, "search": "990 Pro",     "short_name": "990 Pro"},
    {"name": "WD Black SN850X 1TB",            "category": "SSD", "brand": "WD",       "spec": "1TB NVMe M.2 PCIe 4.0", "base_price": 3950, "search": "SN850X",      "short_name": "SN850X"},
    {"name": "Kingston KC3000 1TB",            "category": "SSD", "brand": "Kingston", "spec": "1TB NVMe M.2 PCIe 4.0", "base_price": 3750, "search": "KC3000",      "short_name": "KC3000"},
    {"name": "Micron Crucial T500 1TB",        "category": "SSD", "brand": "Crucial",  "spec": "1TB NVMe M.2 PCIe 4.0", "base_price": 4199, "search": "Crucial T500", "short_name": "T500"},
    {"name": "Micron Crucial P310 1TB",        "category": "SSD", "brand": "Crucial",  "spec": "1TB NVMe M.2 PCIe 4.0", "base_price": 3999, "search": "P310",        "short_name": "P310"},
]

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_products(products_path=None):
    """Load products from a JSON file. Returns a list of product dicts.

    Falls back to the inline PRODUCTS list if the file doesn't exist or
    isn't given.  Products in the file can be minimal (just name + category);
    missing fields are filled with sensible defaults (search=name, brand="").
    """
    if not products_path:
        products_path = os.path.join(_PROJECT_ROOT, "products.json")
    if not os.path.exists(products_path):
        return list(PRODUCTS)
    with open(products_path) as f:
        raw = json.load(f)
    defaults = {p["name"]: p for p in PRODUCTS}
    result = []
    for entry in raw:
        if isinstance(entry, str):
            entry = {"name": entry}
        name = entry["name"]
        d = defaults.get(name, {})
        result.append({
            "name": name,
            "category": entry.get("category", d.get("category", "")),
            "brand": entry.get("brand", d.get("brand", "")),
            "spec": entry.get("spec", d.get("spec", "")),
            "base_price": entry.get("base_price", d.get("base_price", 0)),
            "search": entry.get("search", d.get("search", name)),
            "short_name": d.get("short_name", name),
        })
    return result

def filter_products(products, names):
    """Return only products whose name matches one of the given names (case-insensitive substring)."""
    if not names:
        return products
    lowered = [n.lower() for n in names]
    return [p for p in products if any(term in p["name"].lower() for term in lowered)]

# Map product category → Autobuy category id
AUTOBUY_CATEGORY_IDS = {
    "CPU": 448,
    "GPU": 2067,
    "RAM": 2749,
    "SSD": 5541,
}

STORE_PRICE_FACTOR = {
    "原價屋 CoolPC": 1.0,
    "欣亞 Sinya": 1.02,
    "Autobuy": 0.98,
    "PChome 24h": 1.05,
}

BIGGO_STORE_MAP = {
    "原價屋": "原價屋 CoolPC",
    "欣亞購物網": "欣亞 Sinya",
    "PChome 24h購物": "PChome 24h",
}

# Seller names within marketplace stores (e.g. 蝦皮商城).
# When a seller name from a BigGo product matches one of these keys,
# it overrides the store-level mapping above.
SELLER_MAP = {
    "原價屋Coolpc": "原價屋 CoolPC",
    "原價屋": "原價屋 CoolPC",
    "欣亞": "欣亞 Sinya",
    "欣亞購物網": "欣亞 Sinya",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# ── Helpers ────────────────────────────────────────────────────────

def _parse_sinya_price(price_val):
    """Parse a Sinya price value (string or int) → int."""
    if isinstance(price_val, (int, float)):
        return int(price_val)
    digits = re.sub(r"[^\d]", "", str(price_val))
    return int(digits) if digits else 0


def _normalize(text):
    """Lower-case, strip whitespace, remove common punctuation for matching."""
    t = text.lower().strip()
    # remove parentheses/brackets content that often contains colour or useless info
    t = re.sub(r"[（(][^）)]*[）)]", "", t)
    t = re.sub(r"[《<][^》>]*[》>]", "", t)
    t = re.sub(r"【[^】]*】", "", t)
    t = re.sub(r"[ \u3000]", " ", t)  # narrow no-break space, full-width space
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _keyword_match(text, keywords):
    """Return True if all keywords appear (case-insensitive) in text."""
    t = _normalize(text)
    return all(kw.lower() in t for kw in keywords)


# ── Sinya scraper ─────────────────────────────────────────────────

def sinya_fetch(keyword, max_retries=2):
    """Query Sinya for *keyword* and return a list of {title, price} dicts
    for *standalone products only* (no bundles/PCs).

    ALWAYS tries both the DIY search API (gateway.sinya.com.tw/api/diy/search)
    and the old per-product API (api/search/getdata/1), then merges results
    (deduplicating by title).  This gives the broadest coverage — some
    products appear on only one of the two APIs.
    """
    merged = {}  # title → {title, price}

    def _try_diy():
        url = "https://gateway.sinya.com.tw/api/diy/search"
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, headers=_HEADERS, params={"keyword": keyword}, timeout=20)
                if resp.status_code == 200 and resp.json().get("status") == "success":
                    return resp.json().get("data", [])
            except Exception as e:
                print(f"  [Sinya/DIY] attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        return []

    def _try_old():
        url = f"https://www.sinya.com.tw/api/search/getdata/1?keyword={requests.utils.quote(keyword)}"
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=20)
                if resp.status_code == 200:
                    return resp.json().get("results", [])
            except Exception as e:
                print(f"  [Sinya/Old] attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        return []

    # DIY API
    diy_results = _try_diy()
    for r in _sinya_filter_items(diy_results, keyword):
        key = r["title"].lower()
        existing = merged.get(key)
        if existing is None or r["price"] < existing["price"]:
            merged[key] = r

    # Old API
    old_results = _try_old()
    for r in _sinya_filter_items_old(old_results, keyword):
        key = r["title"].lower()
        existing = merged.get(key)
        if existing is None or r["price"] < existing["price"]:
            merged[key] = r

    if merged:
        items = sorted(merged.values(), key=lambda x: x["price"])
        return items
    return []


def _is_bundle(title_lower):
    """Check if a product title indicates a bundle/pre-built PC.

    Uses regex for the 'pc' keyword to avoid false positives like
    'PCle' (PCIe misspelling) or 'PCIe' in component titles.
    """
    # Simple substring keywords (no risk of false positives)
    simple_kw = [
        "送", "搭機", "套裝", "主機", "組合", "加送", "贈", "加購",
        "救贖", "原價", "福利", "整組", "全套", "套餐", "配",
        "筆電", "laptop", "notebook", "工作站", "電競電腦", "迷你電腦",
        "準系統", "品牌電腦", "捷元", "限量優惠組", "優惠組",
        "+",          # combo deals (e.g. "265K+技嘉 B860...")
        "專案",       # bundle projects (e.g. "U版專案")
        "欣亞",       # Sinya pre-built PCs
        "約", "試",   # "約"→estimated price, "試"→trial/used
        "桌機",       # pre-built desktop PCs (桌機 ≠ 主機)
        "行動工作站",
    ]
    for bw in simple_kw:
        if bw in title_lower:
            return True
    # "pc" — use word-boundary regex to avoid matching "pcle" or "pcie"
    if re.search(r'(?<![a-zA-Z])pc(?![a-zA-Z])', title_lower):
        return True
    return False


def _sinya_filter_items(results, keyword):
    """Filter DIY API results: keep standalone products only, no bundles/PCs."""
    kw_lower = keyword.lower()
    items = []
    for r in results:
        title = r.get("prod_name", "")
        if not title:
            continue
        if kw_lower not in title.lower():
            continue
        if _is_bundle(title.lower()):
            continue
        price = r.get("current_price") or r.get("price", 0)
        try:
            price = int(float(price))
        except (ValueError, TypeError):
            continue
        if price <= 0:
            continue
        items.append({"title": title, "price": price})
    return items


def _sinya_filter_items_old(results, keyword):
    """Filter old API results: keep standalone products only, no bundles/PCs."""
    kw_lower = keyword.lower()
    items = []
    for r in results:
        title = r.get("prod_title", "")
        price_str = r.get("new_price", "")
        price = _parse_sinya_price(price_str)
        if price <= 0:
            continue
        if kw_lower not in title.lower():
            continue
        if _is_bundle(title.lower()):
            continue
        items.append({"title": title, "price": price})
    return items


# ── CoolPC scraper ────────────────────────────────────────────────

def _decode_html_entities(text):
    """Decode common HTML entities (numeric and named) to plain text."""
    # Decode numeric entities first
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    # Named entities
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
        "&#8211;": "–", "&#8212;": "—", "&ndash;": "–", "&mdash;": "—",
        "&nbsp;": " ", "&#8230;": "…",
    }
    for k, v in entities.items():
        text = text.replace(k, v)
    return text


def coolpc_fetch(keyword, max_retries=2):
    """Search CoolPC (WordPress + WooCommerce) for *keyword* using the
    public Store API, and return a list of {title, price} dicts.

    Note: CoolPC's WooCommerce treats blog posts and promotional articles
    as "products", so results are VERY noisy.  This function fetches from
    the GPU category (category=50) and applies aggressive title filtering
    to exclude promos.  Many queries will return 0 usable results.
    """
    api_url = "https://www.coolpc.com.tw/tw/wp-json/wc/store/products"
    params = {
        "search": keyword,
        "per_page": 50,
    }
    for attempt in range(max_retries):
        try:
            resp = requests.get(api_url, headers=_HEADERS, params=params, timeout=20)
            if resp.status_code != 200:
                print(f"  [CoolPC] HTTP {resp.status_code} for '{keyword}'")
                return []
            data = resp.json()
        except Exception as e:
            print(f"  [CoolPC] attempt {attempt + 1} failed: {e}")
            time.sleep(2)
            continue

        # Promo/pure-article categories to exclude
        promo_cats = {"促銷活動", "商品開箱", "原價屋門市|活動|公告",
                       "預購搶購", "展場活動", "品牌電腦", "酷!PC主機"}

        items = []
        for p in data:
            name = p.get("name", "")
            prices = p.get("prices", {})
            price_raw = prices.get("price") or prices.get("regular_price")
            if not name or not price_raw:
                continue
            try:
                price = int(float(price_raw))
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue

            # Decode HTML entities in name
            name = _decode_html_entities(name)
            name = re.sub(r'\s+', ' ', name).strip()

            # Skip if title looks like a promo article (starts with 【 or 《)
            if re.match(r'^[【《]', name):
                continue

            # Skip if title is purely a promo category
            cats = {c["name"] for c in p.get("categories", [])}
            # If ALL categories are promo categories → skip
            if cats and cats.issubset(promo_cats):
                continue

            # Skip known promo/article patterns in the title
            skip_phrases = [
                "搶購", "開箱", "公告", "門市限定", "已截止", "已搶畢",
                "加賽點滴", "一個人的武林", "轟動武林", "預告", "新品促銷",
                "精緻組裝", "完美直播", "全球都在用", "極致輕薄",
                "讓你玩", "包季會員", "送限量", "限定",
                "雙11", "618", "年中慶", "暑假", "快閃",
                "菜單", "再送", "加碼", "體驗機", "限時",
                "創始版", "首賣", "上市", "到貨", "預購",
                "筆電", "筆記型電腦", "筆記本",
            ]
            if any(sp in name for sp in skip_phrases):
                continue

            items.append({"title": name, "price": price})

        if items:
            # Deduplicate
            seen = set()
            unique = []
            for it in items:
                key = _normalize(it["title"])
                if key not in seen:
                    seen.add(key)
                    unique.append(it)
            unique.sort(key=lambda x: x["price"])
            return unique

        return items

    return []


# ── Autobuy scraper ───────────────────────────────────────────────

def autobuy_fetch_category(category_id, max_retries=2):
    """Fetch an Autobuy category product list via the internal order_by
    API endpoint (ajax_prod_cate_order_by_{category_id}_0), which returns
    JSON with name, price, and stock count for every product.

    Products with Stock == 0 (out of stock) are filtered out.
    Returns a list of {title, price} dicts."""
    url = f"https://www.autobuy.tw/ajax_prod_cate_order_by_{category_id}_0"
    headers = {**_HEADERS,
               "Content-Type": "application/json",
               "X-Requested-With": "XMLHttpRequest",
               "Referer": f"https://www.autobuy.tw/3c/cate_{category_id}"}
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                print(f"  [Autobuy] HTTP {resp.status_code} for category {category_id}")
                return []
            data = resp.json()
        except Exception as e:
            print(f"  [Autobuy] attempt {attempt + 1} failed: {e}")
            time.sleep(2)
            continue

        items = []
        for p in data.get("Products", []):
            name = p.get("name", "")
            price = p.get("price")
            stock = p.get("Stock", 0)
            if not name or not price:
                continue
            try:
                price = int(float(price))
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue
            if int(stock) == 0:
                continue
            items.append({"title": name.strip(), "price": price})

        if items:
            seen = set()
            unique = []
            for it in items:
                key = _normalize(it["title"])
                if key not in seen:
                    seen.add(key)
                    unique.append(it)
            unique.sort(key=lambda x: x["price"])
            return unique

        return items

    return []


# ── BigGo scraper ─────────────────────────────────────────────────

_BIGGO_SKIP_TITLES = [
    "筆電", "電競筆電", "laptop", "notebook",
    "電競機", "平台", "DIY",
    "福利品", "福利", "二手", "中古", "已下架",
]

def biggo_fetch(keyword, max_retries=2):
    """Search BigGo price comparison for *keyword* and return a list of
    {title, price, store_name} dicts.

    BigGo aggregates prices from 30+ Taiwan stores including CoolPC,
    Sinya, PChome, momo, Yahoo, etc.  This is our primary source for
    all stores except Autobuy (which isn't on BigGo).
    """
    url = f"https://biggo.com.tw/s/{requests.utils.quote(keyword)}/"
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"  [BigGo] HTTP {resp.status_code} for '{keyword}'")
                return []
            html = resp.text
        except Exception as e:
            print(f"  [BigGo] attempt {attempt + 1} failed: {e}")
            time.sleep(2)
            continue

        items = []
        # Split on data-info="true" to isolate each product card
        blocks = re.split(r'<div[^>]*data-info="true"[^>]*>', html)

        for block in blocks[1:]:
            title_m = re.search(r'<a\b[^>]*>([^<]+)</a>', block)
            if not title_m:
                continue
            title = title_m.group(1).strip()

            title_lower = title.lower()
            if any(sp.lower() in title_lower for sp in _BIGGO_SKIP_TITLES):
                continue

            price_m = re.search(r'data-price="true"[^>]*>\s*\$?([0-9,]+)', block)
            if not price_m:
                continue
            try:
                price = int(price_m.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue

            store_m = re.search(
                r'store-name-container[^>]*>.*?<span[^>]*>([^<]+)</span>',
                block, re.DOTALL,
            )
            if not store_m:
                continue
            store_name = store_m.group(1).strip()

            # Extract seller name within marketplace stores (e.g. 蝦皮商城)
            seller_m = re.search(
                r'StoreName_seller[^>]*>.*?<span[^>]*>([^<]+)</span>',
                block, re.DOTALL,
            )
            seller = seller_m.group(1).strip() if seller_m else ""

            # Resolve to internal store name: check seller first, then store name
            internal_store = None
            if seller:
                for seller_key, internal in SELLER_MAP.items():
                    if seller_key.lower() in seller.lower():
                        internal_store = internal
                        break
            if not internal_store:
                internal_store = BIGGO_STORE_MAP.get(store_name)
            if not internal_store:
                continue

            items.append({"title": title, "price": price, "store_name": internal_store})

        if items:
            seen = set()
            unique = []
            for it in items:
                key = _normalize(it["title"])
                if key not in seen:
                    seen.add(key)
                    unique.append(it)
            return unique
        return []

    return []


# ── CoolPC category scraper (WooCommerce API — DEAD REFERENCE) ─────
#
# The WooCommerce API at /tw/wp-json/wc/store/products returns 100%
# promotional blog content as "products" — CPU category (id=30) has
# zero real SKUs, GPU/etc categories return false positives when
# generic spec keywords (rtx, ddr5, 1tb) happen to appear in promos.
#
# Replaced by coolpc_fetch_from_evaluate() which scrapes the real
# PC configurator at https://coolpc.com.tw/evaluate.php.
#
# Keep this code as dead reference (like BigGo) in case the
# evaluate.php approach ever needs fallback.

COOLPC_CATEGORY_IDS = {
    "CPU": 30, "GPU": 50, "RAM": 64, "SSD": 182,
}

_COOLPC_PROMO_PHRASES = [
    "開箱", "報價", "搶購", "截止", "限定", "送", "贈", "加碼",
    "快閃", "暑假", "雙11", "618", "年中慶", "預告", "預購",
    "上市", "到貨", "首賣", "公告", "門市", "限量", "限時",
    "已截止", "已搶畢", "加賽", "轟動武林", "一個人的武林",
    "精緻組裝", "完美直播", "全球都在用", "極致輕薄",
    "讓你玩", "包季會員", "送限量", "體驗機",
    "菜單", "再送", "創始版", "WirForce", "GamForce",
    "直播間", "開播", "裝酷", "原價屋門市",
    "立即搶購", "即刻搶購", "倒數",
    "系列顯示卡搭主板送", "系列顯示卡搭",
    "折五百", "折一千", "折二千", "免三仟", "不用六仟",
    "超品日", "限定優惠", "限定活動",
    "加碼送", "限量加碼",
]

_COOLPC_MIN_PRICE = {
    "CPU": 5000, "GPU": 5000, "RAM": 1000, "SSD": 1000,
}

# ── CoolPC evaluate.php scraper (NEW) ─────────────────────────────

# Map product category → evaluate.php <SELECT> name attribute
COOLPC_EVALUATE_SELECT_MAP = {
    "CPU": "n4",
    "GPU": "n12",
    "RAM": "n6",
    "SSD": "n7",
}


def coolpc_fetch_from_evaluate(max_retries=2):
    """Fetch real product prices from CoolPC's evaluate.php page — a JS-based
    PC configurator that contains <SELECT> elements with real product SKUs
    and current prices.

    Replaces the old coolpc_fetch_category() which used the WooCommerce API
    (100% promo blog content for CPU, false positives for other categories).

    Single HTTP request fetches all 4 categories at once.

    Returns a dict mapping category name → list of {title, price} dicts:
        {"CPU": [...], "GPU": [...], "RAM": [...], "SSD": [...]}
    """
    url = "https://coolpc.com.tw/evaluate.php"

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=30)
            if resp.status_code != 200:
                print(f"  [CoolPC/evaluate] HTTP {resp.status_code}")
                return {}
            html = resp.text
        except Exception as e:
            print(f"  [CoolPC/evaluate] attempt {attempt + 1} failed: {e}")
            time.sleep(2)
            continue

        # Extract all <SELECT> elements with their name attributes
        select_pattern = re.compile(
            r'<SELECT[^>]*name=(\w+)[^>]*>(.*?)</SELECT>',
            re.IGNORECASE | re.DOTALL,
        )

        # Build a cache: select_name → list of inner-option HTML blocks
        select_cache = {}
        for m in select_pattern.finditer(html):
            name = m.group(1).lower()
            inner = m.group(2)
            options = re.findall(r'<OPTION[^>]*>(.*?)</OPTION>', inner, re.I)
            select_cache[name] = options

        result = {}
        for cat_name, sel_name in COOLPC_EVALUATE_SELECT_MAP.items():
            options = select_cache.get(sel_name.lower(), [])
            items = []

            for opt_text in options:
                decoded = _decode_html_entities(opt_text).strip()

                # Skip promo banners
                if decoded.startswith('❤') or decoded.startswith('↪'):
                    continue

                # Extract price(s) — some entries have ranges like
                # "..., $26890→$25890 ✔ ✔" where the lower price is the
                # real/discounted price.
                prices_found = re.findall(r'\$([0-9,]+)', decoded)
                if not prices_found:
                    continue
                prices = [int(p.replace(",", "")) for p in prices_found]
                price = min(prices)  # take the lower price for ranges

                if price <= 0:
                    continue

                # Extract title: remove everything from the last
                # ", $PRICE" pattern to the end of the string.
                title = re.sub(
                    r',\s*\$[0-9,]+(?:\s*[→➔➡▶>]\s*\$[0-9,]+)?.*$',
                    "",
                    decoded,
                ).strip()

                if not title:
                    continue

                items.append({"title": title, "price": price})

            if items:
                # Deduplicate by normalized title
                seen = set()
                unique = []
                for it in items:
                    key = _normalize(it["title"])
                    if key not in seen:
                        seen.add(key)
                        unique.append(it)
                unique.sort(key=lambda x: x["price"])
                result[cat_name] = unique
            else:
                result[cat_name] = []

        return result

    return {}


# ── Product matcher ───────────────────────────────────────────────

def _extract_vram_gb(name):
    """Extract VRAM capacity in GB from a product/candidate name.

    Returns an int (e.g. 8, 16) or None if not found.

    Handles patterns like '8GB', '16GB', '8G', 'O8G', 'O16G', '-8GB',
    and also looks for combined tokens like 'rtx5060ti-o8g'.
    """
    m = re.search(r'(?<!\d)(\d+)\s*(?:gb|g)\b', name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Also check patterns like "o8g", "o16g" (ASUS naming)
    m = re.search(r'[oO](\d+)[gG]\b', name)
    if m:
        return int(m.group(1))
    return None


def _has_variant_suffix(text, suffix):
    """True if `suffix` appears as a standalone word or concatenated with
    model numbers (e.g. '5070ti'), but NOT embedded inside other English
    words (e.g. 'ti' inside 'edition').

    Uses a regex that requires the suffix to be preceded by a non-lowercase-letter
    (or start-of-string) and followed by a non-lowercase-letter (or end-of-string).
    This allows concatenations like ``5070ti`` (digit before) while rejecting
    ``edition`` (letter before).
    """
    pattern = r'(?:^|(?<=[^a-z]))' + re.escape(suffix) + r'(?=[^a-z]|$)'
    return bool(re.search(pattern, text))


# Max length for store product titles stored in the DB (truncated to keep
# database size manageable while preserving enough "edition"/brand/model
# keywords for verification).
_MAX_STORE_TITLE = 120


def _truncate_title(title):
    return title[:_MAX_STORE_TITLE] if len(title) > _MAX_STORE_TITLE else title


def _match_product_by_name(product_name, candidates):
    """Given a product name (e.g. 'NVIDIA RTX 5080') and a list of
    {title, price} candidates from a store, find the best match and
    return (price, matched_title) or None.

    Strategy:
      1. Build a set of required keywords for the product.
      2. Find candidates that contain those keywords.
      3. For GPU chips with many brand variants, pick the cheapest.
      4. Penalize candidates whose model suffix differs from the target
         (e.g. avoid matching 'RX 9070 GRE' when we want 'RX 9070').
      5. Penalize VRAM mismatch (e.g. 8GB vs 16GB).
    """
    norm_name = _normalize(product_name)
    target_words = set(norm_name.split())

    # Extract VRAM from product name
    target_vram = _extract_vram_gb(product_name)

    # Extract meaningful keywords from the product name
    stopwords = {"nvidia", "amd", "intel", "corsair", "g.skill", "kingston",
                 "samsung", "wd", "crucial", "ryzen", "core", "series"}

    name_words = [w for w in norm_name.split() if w not in stopwords and len(w) > 1]

    # Known variant suffixes that define a *different* product tier.
    # These should never match unless the target product name also contains them.
    variant_suffixes = {"kf", "xt", "gre", "xtx", "super", "ultra", "lite", "max", "ti", "ks"}

    # For each candidate, compute a match score
    scored = []
    for c in candidates:
        c_norm = _normalize(c["title"])
        c_words = set(c_norm.split())

        # Score based on how many name_words appear in the candidate
        matches = sum(1 for w in name_words if w in c_norm)
        # Need at least 2 keyword matches to avoid false positives,
        # but for products with only 1 keyword (e.g. CPUs after stopword removal),
        # require that 1 keyword to match.
        min_required = min(2, len(name_words))
        if matches < min_required:
            continue

        # Penalize bundles
        bundle_penalty = 0
        for bw in ["搭機", "套裝", "主機", "裝機配", "送", "救贖", "福利"]:
            if bw.lower() in c_norm:
                bundle_penalty += 50

        # Penalise variant mismatch: if one side has a tier suffix the other
        # lacks, it's the wrong product.  Uses _has_variant_suffix on the
        # candidate side (handles concatenation like '5070ti') while the
        # target side uses word-set membership (target names always well-spaced).
        variant_penalty = 0
        for vs in variant_suffixes:
            in_target = vs in target_words
            in_candidate = _has_variant_suffix(c_norm, vs)
            if in_candidate != in_target:
                variant_penalty += 60  # wrong product tier

        # Penalise VRAM mismatch (e.g. 8GB vs 16GB)
        vram_penalty = 0
        if target_vram is not None:
            candidate_vram = _extract_vram_gb(c["title"])
            if candidate_vram is not None and candidate_vram != target_vram:
                vram_penalty = 80  # heavy: wrong VRAM capacity

        score = matches * 10 - bundle_penalty - variant_penalty - vram_penalty
        # Bonus for exact name match or very high overlap
        if norm_name in c_norm or product_name.lower() in c_norm:
            score += 100

        scored.append((score, c["price"], c))

    if not scored:
        return None

    # Sort by score descending, then price ascending (cheapest among best matches)
    scored.sort(key=lambda x: (-x[0], x[1]))
    best_score = scored[0][0]
    # Minimum score threshold: 2 clean keyword matches = 20, anything below
    # indicates variant mismatch, bundle, or too many false positives.
    # For products with only 1 keyword (e.g. CPUs after stopword removal),
    # a perfect score is 10 — relax the threshold accordingly.
    if len(name_words) == 1:
        if best_score < 5:
            return None
    elif best_score < 15:
        return None
    best = scored[0]
    return (best[1], _truncate_title(best[2]["title"]))


# ── Orchestrator ──────────────────────────────────────────────────

def scrape_real_prices(products=None):
    """Scrape prices from Sinya, CoolPC, and Autobuy.

    BigGo is no longer usable (Cloudflare).  PChome is also Cloudflare-blocked
    and will remain synthetic for now.

    Args:
        products: optional list of product dicts (defaults to PRODUCTS).

    Returns:
      {
        "原價屋 CoolPC": {product_name: {"price": price, "title": title}, ...},
        "欣亞 Sinya":    {product_name: {"price": price, "title": title}, ...},
        "PChome 24h":    {product_name: {"price": price, "title": title}, ...},
        "Autobuy":       {product_name: {"price": price, "title": title}, ...},
      }
    """
    print("=" * 55)
    print("  Scraping real prices (Sinya + CoolPC + Autobuy)")
    print("=" * 55)

    results = {
        "原價屋 CoolPC": {},
        "欣亞 Sinya": {},
        "PChome 24h": {},
        "Autobuy": {},
    }

    # ── 1. Sinya: per-product API search ──
    print("\n[Sinya]  Searching all products...")
    for prod in (products or PRODUCTS):
        kw = prod.get("search", prod["name"])
        print(f"  Searching '{kw}'...", end=" ", flush=True)
        items = sinya_fetch(kw)
        if not items:
            print("no results")
            time.sleep(0.2)
            continue
        match = _match_product_by_name(prod["name"], items)
        if match is not None:
            price, title = match
            results["欣亞 Sinya"][prod["name"]] = {"price": price, "title": title}
            print(f"✓ NT${price:,}  [{title[:50]}]")
        else:
            print(f"no match ({len(items)} candidates)")
        time.sleep(0.2)

    # ── 2. CoolPC: evaluate.php scrape (replaces WooCommerce API) ──
    print("\n[CoolPC/evaluate]")
    coolpc_inventory = coolpc_fetch_from_evaluate()
    for cat in ["CPU", "GPU", "RAM", "SSD"]:
        count = len(coolpc_inventory.get(cat, []))
        print(f"  Category '{cat}': {count} products")
    time.sleep(0.5)

    for prod in (products or PRODUCTS):
        cat_items = coolpc_inventory.get(prod["category"], [])
        if not cat_items:
            continue
        match = _match_product_by_name(prod["name"], cat_items)
        if match is not None:
            price, title = match
            results["原價屋 CoolPC"][prod["name"]] = {"price": price, "title": title}
            print(f"  '{prod['name']}' → NT$ {price:,}  [{title[:50]}]")

    # ── 3. Autobuy: category-level fetch ──
    print("\n[Autobuy]")
    autobuy_inventory = {}
    for cat in ["CPU", "GPU", "RAM", "SSD"]:
        cat_id = AUTOBUY_CATEGORY_IDS.get(cat)
        if not cat_id:
            continue
        print(f"  Fetching category '{cat}' (cate_{cat_id})...", end=" ", flush=True)
        items = autobuy_fetch_category(cat_id)
        print(f"{len(items)} products")
        autobuy_inventory[cat] = items
        time.sleep(0.5)

    for prod in (products or PRODUCTS):
        cat_items = autobuy_inventory.get(prod["category"], [])
        if not cat_items:
            continue
        match = _match_product_by_name(prod["name"], cat_items)
        if match is not None:
            price, title = match
            results["Autobuy"][prod["name"]] = {"price": price, "title": title}
            print(f"  '{prod['name']}' → NT$ {price:,}  [{title[:50]}]")

    # Summary
    print("\n" + "=" * 55)
    active_stores = ["原價屋 CoolPC", "欣亞 Sinya", "Autobuy"]
    total_real = 0
    total_possible = len(PRODUCTS) * len(active_stores)
    for store_name in active_stores + ["PChome 24h"]:
        count = len(results[store_name])
        pct = round(count / len(PRODUCTS) * 100)
        total_real += count if store_name != "PChome 24h" else 0
        print(f"  {store_name:20s} {count:>2}/{len(PRODUCTS)} ({pct:>2}%)")
    print(f"  {'TOTAL':20s} {total_real:>2}/{total_possible} ({round(total_real/total_possible*100)}%)")
    print("=" * 55)

    return results


# ── Price generation (synthetic fallback) ────────────────────────

def generate_price(base_price, store_name, day_offset=0):
    factor = STORE_PRICE_FACTOR.get(store_name, 1.0)
    daily_noise = random.gauss(0, 0.02)
    trend = math.sin(day_offset * 0.05) * 0.03
    price = base_price * factor * (1 + daily_noise + trend)
    return max(round(price / 100) * 100, 100)


# ── Seeding ───────────────────────────────────────────────────────

def seed_demo_data(db, days=45, real_prices=None, products=None):
    """Seed the database with historical data.

    If *real_prices* is provided (the dict returned by scrape_real_prices()),
    the latest price for each store+product combo will be anchored to the
    real scraped price.  PChome always stays synthetic.

    Historical data (past *days* days) is synthesised around the current
    (real or synthetic) price anchor.
    """
    db.init_db()
    for store in STORES:
        db.upsert_store(store["name"], store["url"])
    db.commit()

    now = datetime.now()
    total = 0

    for prod in (products or PRODUCTS):
        product_id = db.upsert_product(prod["name"], prod["category"], prod["brand"], prod["spec"], msrp=prod.get("base_price", 0))
        rng = random.Random(f"{prod['name']}-seed")

        for store in STORES:
            store_name = store["name"]
            store_id = db.upsert_store(store_name)

            # Determine if we have a real scraped price for this store+product
            has_real = False
            real_price = None
            if real_prices and store_name in real_prices:
                real_price = real_prices[store_name].get(prod["name"])
                if real_price is not None:
                    has_real = True

            for d in range(days, -1, -1):
                ts = now - timedelta(days=d, hours=rng.randint(8, 20), minutes=rng.randint(0, 59))

                if has_real and d == 0:
                    price = real_price
                elif has_real:
                    daily_noise = rng.gauss(0, 0.015)
                    trend = math.sin(d * 0.05) * 0.02
                    price = real_price * (1 + daily_noise + trend)
                    price = max(round(price / 100) * 100, 100)
                else:
                    price = generate_price(prod["base_price"], store_name, day_offset=d)

                db.record_price(product_id, store_id, price, ts.isoformat())
                total += 1

        db.commit()

    print(f"Seeded {len(PRODUCTS)} products, {len(STORES)} stores, {days + 1} days = {total} records")
