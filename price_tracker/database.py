import sqlite3
import os
from datetime import datetime, timedelta

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def get_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(os.path.join(DB_DIR, "prices.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class DB:
    def __init__(self):
        self.conn = None

    def open(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.conn = sqlite3.connect(os.path.join(DB_DIR, "prices.db"))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        return self

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                brand TEXT DEFAULT '',
                spec TEXT DEFAULT '',
                msrp INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                store_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                is_synthetic INTEGER DEFAULT 0,
                recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (store_id) REFERENCES stores(id)
            );
            CREATE INDEX IF NOT EXISTS idx_snap_product ON price_snapshots(product_id);
            CREATE INDEX IF NOT EXISTS idx_snap_store ON price_snapshots(store_id);
            CREATE INDEX IF NOT EXISTS idx_snap_date ON price_snapshots(recorded_at);
        """)
        self.conn.commit()
        # Migrate existing DB if columns are missing
        for col_sql in [
            "ALTER TABLE price_snapshots ADD COLUMN is_synthetic INTEGER DEFAULT 0",
            "ALTER TABLE products ADD COLUMN msrp INTEGER DEFAULT 0",
        ]:
            try:
                self.conn.execute(col_sql)
                self.conn.commit()
            except Exception:
                pass  # Column already exists

    def upsert_product(self, name, category, brand="", spec="", msrp=0):
        self.conn.execute(
            "INSERT INTO products(name, category, brand, spec, msrp) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET category=excluded.category, brand=excluded.brand, spec=excluded.spec, msrp=excluded.msrp",
            (name, category, brand, spec, msrp),
        )
        return self.conn.execute("SELECT id FROM products WHERE name = ?", (name,)).fetchone()["id"]

    def upsert_store(self, name, url=""):
        self.conn.execute(
            "INSERT INTO stores(name, url) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET url=excluded.url",
            (name, url),
        )
        return self.conn.execute("SELECT id FROM stores WHERE name = ?", (name,)).fetchone()["id"]

    def record_price(self, product_id, store_id, price, recorded_at=None, is_synthetic=0):
        if recorded_at:
            self.conn.execute(
                "INSERT INTO price_snapshots(product_id, store_id, price, is_synthetic, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (product_id, store_id, price, is_synthetic, recorded_at),
            )
        else:
            self.conn.execute(
                "INSERT INTO price_snapshots(product_id, store_id, price, is_synthetic) VALUES (?, ?, ?, ?)",
                (product_id, store_id, price, is_synthetic),
            )

    def commit(self):
        self.conn.commit()

    def get_latest_prices(self):
        rows = self.conn.execute("""
            SELECT p.name, p.category, p.brand, p.spec, p.msrp,
                   s.name AS store, ps.price, ps.recorded_at,
                   ps.is_synthetic
            FROM price_snapshots ps
            JOIN products p ON ps.product_id = p.id
            JOIN stores s ON ps.store_id = s.id
            WHERE ps.id IN (
                SELECT MAX(id) FROM price_snapshots GROUP BY product_id, store_id
            )
            ORDER BY p.category, p.name, s.name
        """).fetchall()
        return [dict(r) for r in rows]

    def get_price_history(self, product_name, days=30):
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.conn.execute("""
            SELECT s.name AS store, ps.price, ps.recorded_at,
                   ps.is_synthetic
            FROM price_snapshots ps
            JOIN products p ON ps.product_id = p.id
            JOIN stores s ON ps.store_id = s.id
            WHERE p.name = ? AND ps.recorded_at >= ?
            ORDER BY ps.recorded_at, s.name
        """, (product_name, since)).fetchall()
        return [dict(r) for r in rows]

    def get_all_products(self):
        rows = self.conn.execute("""
            SELECT DISTINCT p.name, p.category, p.brand, p.spec, p.msrp
            FROM products p
            ORDER BY p.category, p.name
        """).fetchall()
        return [dict(r) for r in rows]

    def get_stores(self):
        rows = self.conn.execute("SELECT * FROM stores").fetchall()
        return [dict(r) for r in rows]

    def get_latest_by_product(self):
        rows = self.conn.execute("""
            SELECT p.name, p.category, p.brand, p.spec, p.msrp,
                   ps.price, s.name AS store, ps.recorded_at,
                   ps.is_synthetic
            FROM price_snapshots ps
            JOIN products p ON ps.product_id = p.id
            JOIN stores s ON ps.store_id = s.id
            WHERE ps.id IN (
                SELECT MAX(id) FROM price_snapshots GROUP BY product_id, store_id
            )
            ORDER BY p.category, p.name
        """).fetchall()
        result = {}
        for r in rows:
            d = dict(r)
            base = result.setdefault(d["name"], {"name": d["name"], "category": d["category"], "brand": d["brand"], "spec": d["spec"], "msrp": d["msrp"], "prices": {}})
            base["prices"][d["store"]] = {"price": d["price"], "date": d["recorded_at"], "is_synthetic": d["is_synthetic"]}
        return list(result.values())
