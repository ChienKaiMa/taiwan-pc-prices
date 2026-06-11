import json
import os
import mimetypes
import threading
import random
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from price_tracker.database import DB
from price_tracker.scraper import scrape_real_prices, PRODUCTS, STORES

PORT = int(os.environ.get("PORT", 8080))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "templates")

# ── Background price-update scheduler ────────────────────────────────
# Runs ~4 times daily (every 6 hours ±30 min jitter) to keep prices fresh.
# Uses its own DB connection to stay thread-safe.

SCRAPE_INTERVAL = 6 * 3600          # 6 hours in seconds
SCRAPE_JITTER = 30 * 60             # ±30 minutes

_scrape_lock = threading.Lock()
_scrape_running = False

def _record_prices():
    """Scrape real prices and record a new snapshot for every product+store."""
    global _scrape_running
    with _scrape_lock:
        _scrape_running = True
    print("[scheduler] Starting price scrape...")
    t0 = time.time()
    try:
        real = scrape_real_prices()
    except Exception as exc:
        print(f"[scheduler] Scrape failed: {exc}")
        with _scrape_lock:
            _scrape_running = False
        return
    elapsed = time.time() - t0
    print(f"[scheduler] Scrape done in {elapsed:.0f}s, recording snapshots...")

    db = DB()
    db.open()
    try:
        now = datetime.now()
        total = 0
        for prod in PRODUCTS:
            pid = db.upsert_product(prod["name"], prod["category"], prod.get("brand", ""), prod.get("spec", ""), msrp=prod.get("base_price", 0))
            for store in STORES:
                real_price = real.get(store["name"], {}).get(prod["name"])
                if real_price is None:
                    continue  # skip — no real price available
                sid = db.upsert_store(store["name"], store.get("url", ""))
                db.record_price(pid, sid, real_price, now.isoformat(), 0)
                total += 1
        db.commit()
        print(f"[scheduler] Recorded {total} real snapshots at {now.isoformat()}")
    except Exception as exc:
        print(f"[scheduler] DB write failed: {exc}")
    finally:
        db.close()
        with _scrape_lock:
            _scrape_running = False


def _scheduler_loop():
    """Background loop: scrape every ~6 hours with random jitter."""
    while True:
        # First run immediately on startup
        _record_prices()
        # Then sleep for 6h ± jitter
        delay = SCRAPE_INTERVAL + random.randint(-SCRAPE_JITTER, SCRAPE_JITTER)
        print(f"[scheduler] Next scrape in {delay/3600:.1f} hours")
        time.sleep(delay)


def start_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="price-scheduler")
    t.start()
    print(f"[scheduler] Started (interval={SCRAPE_INTERVAL}s ±{SCRAPE_JITTER}s)")


# ── HTTP Server ─────────────────────────────────────────────────────

_db = DB()


class PriceServer(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/prices":
            self._send_json(_db.get_latest_by_product())
        elif path == "/api/history":
            product = params.get("product", [None])[0]
            days = int(params.get("days", [30])[0])
            if product:
                self._send_json(_db.get_price_history(product, days))
            else:
                self._send_error("Missing product parameter")
        elif path == "/api/products":
            self._send_json(_db.get_all_products())
        elif path == "/api/stores":
            self._send_json(_db.get_stores())
        elif path == "/api/scrape-status":
            with _scrape_lock:
                running = _scrape_running
            self._send_json({"running": running})
        elif path == "/api/scrape":
            # Manually trigger a scrape (runs in background)
            threading.Thread(target=_record_prices, daemon=True).start()
            self._send_json({"status": "scrape started"})
        elif path == "/" or path == "":
            self._serve_static("index.html")
        else:
            self._serve_static(path.lstrip("/"))

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, msg, status=400):
        self._send_json({"error": msg}, status)

    def _serve_static(self, filename):
        filepath = os.path.join(STATIC_DIR, filename)
        if not os.path.isfile(filepath):
            self._send_error("Not Found", 404)
            return
        mime, _ = mimetypes.guess_type(filename)
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {args[0]} {args[1]} {args[2]}")


def start_server():
    _db.open()
    start_scheduler()
    server = HTTPServer(("0.0.0.0", PORT), PriceServer)
    print(f"Server running at http://localhost:{PORT}")
    print(f"Dashboard: http://localhost:{PORT}/")
    print(f"API:       http://localhost:{PORT}/api/prices")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
        _db.close()


if __name__ == "__main__":
    start_server()
