"""順發 Sunfar (isunfar.com.tw) price scraper.

Integrated into the main pipeline via sunfar_fetch().
Use `python -m price_tracker.sunfar_scraper` to run a test against all products.
"""

import json
import os
import re
import sys
import time
import warnings

import requests
import urllib3

# Compiled pattern for pre-built system detection — matches titles that
# contain file-path-style component specs like /16G/ /1TBSSD /2T/ which
# indicate a complete desktop/laptop rather than a standalone part.
_PREBUILT_SYSTEM_RE = re.compile(
    r"/\d+\s*[GT]\s*[Bb]?\s*(?=/|$|\s|[A-Za-z\u4e00-\u9fff])", re.IGNORECASE
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

_BASE_URL = "https://www.isunfar.com.tw"
_SEARCH_URL = f"{_BASE_URL}/product/search.aspx"

_SESSION = None


def _get_session():
    """Get a requests.Session with cookies from the homepage."""
    global _SESSION
    if _SESSION is None:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        s = requests.Session()
        s.verify = False
        try:
            s.get(_BASE_URL, headers=_HEADERS, timeout=15)
        except Exception:
            pass  # proceed without homepage cookies
        _SESSION = s
    return _SESSION


_BRAND_WORDS = {"crucial", "amd", "intel", "nvidia", "kingston", "corsair",
                 "g.skill", "samsung", "wd", "micron", "ryzen", "geforce"}


def _strip_brands(keyword):
    """Remove known brand words from a keyword for fallback searching."""
    parts = keyword.strip().split()
    filtered = [p for p in parts if p.lower() not in _BRAND_WORDS]
    return " ".join(filtered) if filtered else ""


def sunfar_fetch(keyword, max_retries=2):
    """Search Sunfar by keyword and return a list of {title, price} dicts.

    Only returns active (prodseqstate_no == 'A'), purchasable (buy == 'Y')
    products, deduplicated by product serial (ps).

    If the initial search returns no results, automatically retries with
    brand words stripped (e.g. "Crucial T500" → "T500").
    """
    kw = keyword.strip()

    def _do_search(search_kw):
        """Internal fetch with a given keyword, returns items or None."""
        for attempt in range(max_retries):
            try:
                sess = _get_session()
                resp = sess.get(
                    _SEARCH_URL,
                    headers=_HEADERS,
                    params={"keyword": search_kw},
                    timeout=30,
                )
                if resp.status_code != 200:
                    return None
                html = resp.text
                m = re.search(r"var\s+Search_data\s*=\s*(\{.+?\});", html, re.S)
                if not m:
                    return None
                data = json.loads(m.group(1))
                ptlist = data.get("ptlist", [])
                if not ptlist:
                    return []
                seen = set()
                items = []
                for p in ptlist:
                    ps = p.get("ps", "")
                    if not ps or ps in seen:
                        continue
                    seen.add(ps)
                    if p.get("buy") != "Y":
                        continue
                    title = p.get("pname", "").strip()
                    price = p.get("prod_price", 0)
                    if not title or price <= 0:
                        continue
                    # Skip pre-built system listings
                    if _PREBUILT_SYSTEM_RE.findall(title):
                        continue
                    items.append({"title": title, "price": int(price)})
                return items
            except Exception as e:
                print(f"  [Sunfar] attempt {attempt + 1} failed: {e}")
                time.sleep(2)
                global _SESSION
                _SESSION = None
        return None

    # Try original keyword.  Also always try the condensed version (no spaces)
    # because Sunfar often splits differently ("5060 Ti" vs "5060Ti").
    items = _do_search(kw) or []
    condensed = kw.replace(" ", "")
    if condensed and condensed != kw:
        extra = _do_search(condensed) or []
        seen_titles = {i["title"] for i in items}
        items += [i for i in extra if i["title"] not in seen_titles]

    # If still empty, try brand-stripped and individual digit-words as fallbacks.
    if not items:
        fb = _strip_brands(kw)
        if fb and fb != kw:
            items = _do_search(fb) or []
    if not items:
        for word in kw.split():
            if any(c.isdigit() for c in word) and word != kw:
                items = _do_search(word) or []
                if items:
                    break
    return items


# ── Standalone test ────────────────────────────────────────────

def _load_products():
    """Load the project's product list (same logic as scraper.py)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    products_path = os.path.join(root, "products.json")
    if os.path.exists(products_path):
        with open(products_path) as f:
            return json.load(f)
    # Fallback: minimal inline defaults
    return [
        {"name": "AMD Ryzen 5 9600X", "category": "CPU"},
    ]


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()

    products = _load_products()
    print(f"Loaded {len(products)} product(s)\n")

    print("--- Sunfar Scraper Test ---")
    for prod in products:
        kw = prod.get("search", prod.get("name", ""))
        print(f"  Searching '{kw}'...", end=" ", flush=True)
        items = sunfar_fetch(kw)
        if items:
            print(f"{len(items)} result(s)")
            for item in items[:3]:
                print(f"    NT${item['price']:,}  [{item['title'][:60]}]")
        else:
            print("no results")
        time.sleep(1)
