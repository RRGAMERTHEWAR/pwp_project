"""SQLite Database Layer for the Customer Billing System.

HOW TO EDIT & USE:
- This file contains all raw SQL interactions (CREATE, INSERT, UPDATE, SELECT).
- Never write SQL directly in UI files; define functions here and call them from the UI.
- All connections use row_factory = sqlite3.Row for dict-like column access (e.g., row["name"]).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import bcrypt
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

from core.calculations import Bill, LineItem

DB_FILENAME = "billing_system.db"

# Absolute path to billing_system.db in the project root directory
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", DB_FILENAME)
DB_PATH = os.path.abspath(DB_PATH)


# ==========================================
# Database Table Schemas
# ==========================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    phone           TEXT,
    email           TEXT,
    loyalty_balance INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL,
    price REAL    NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    full_name     TEXT,
    role          TEXT    NOT NULL DEFAULT 'cashier'
                           CHECK (role IN ('cashier', 'admin'))
);

CREATE TABLE IF NOT EXISTS bills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL,
    subtotal        REAL    NOT NULL,
    discount        REAL    NOT NULL,
    points_used     INTEGER NOT NULL DEFAULT 0,
    points_redeemed REAL    NOT NULL DEFAULT 0,
    tax             REAL    NOT NULL,
    loyalty_points  INTEGER NOT NULL,
    total           REAL    NOT NULL,
    payment_method  TEXT    NOT NULL DEFAULT 'Cash',
    created_at      TEXT    NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    action      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS bill_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id      INTEGER NOT NULL,
    product_id   INTEGER,
    description  TEXT    NOT NULL,
    qty          INTEGER NOT NULL,
    unit_price   REAL    NOT NULL,
    line_total   REAL    NOT NULL,
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);
"""

# New columns added to pre-existing databases without destroying their data.
_MIGRATIONS = [
    ("customers", "loyalty_balance", "INTEGER NOT NULL DEFAULT 0"),
    ("bills", "points_used", "INTEGER NOT NULL DEFAULT 0"),
    ("bills", "points_redeemed", "REAL NOT NULL DEFAULT 0"),
    ("bill_items", "product_id", "INTEGER"),
    ("bills", "payment_method", "TEXT NOT NULL DEFAULT 'Cash'"),
    ("products", "cost_price", "REAL NOT NULL DEFAULT 0.0"),
    ("bill_items", "unit_cost", "REAL NOT NULL DEFAULT 0.0"),
    ("bills", "user_id", "INTEGER"),
    ("products", "min_stock", "INTEGER NOT NULL DEFAULT 5"),
]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a sqlite3 connection with FK enforcement + row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist and run any needed migrations."""
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, column, ddl in _MIGRATIONS:
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            create_user("admin", "admin123", full_name="Administrator", role="admin")
            create_user("cashier", "cash123", full_name="Cashier", role="cashier")


# --- password hashing / auth --------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")



def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash (supports legacy SHA256 migration)."""
    try:
        if "$" in stored and not stored.startswith("$2b$") and not stored.startswith("$2a$"):
            # Legacy SHA256 format: salt$digest
            salt, digest = stored.split("$", 1)
            check = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
            return secrets.compare_digest(check, digest)

        # Bcrypt format
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
    except Exception:
        return False


def verify_login(username: str, password: str) -> dict | None:
    """Return the user dict if credentials match, else None.
    Upgrades legacy SHA256 passwords to bcrypt on successful login.
    """
    username = (username or "").strip()
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        return None

    stored_hash = row["password_hash"]
    if not _verify_password(password, stored_hash):
        return None

    # Lazy Migration: Upgrade to bcrypt if stored as legacy SHA256
    if "$" in stored_hash and not stored_hash.startswith("$2b$") and not stored_hash.startswith("$2a$"):
        new_hash = _hash_password(password)
        with connect() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row["id"]))

    user = dict(row)
    user.pop("password_hash", None)
    return user


def create_user(
    username: str, password: str, *, full_name: str = "", role: str = "cashier"
) -> None:
    """Insert a new user. Raises sqlite3.IntegrityError if the name is taken."""
    if role not in ("cashier", "admin"):
        raise ValueError("role must be 'cashier' or 'admin'")
    with connect() as conn:
        conn.execute(
            """INSERT INTO users (username, password_hash, full_name, role)
               VALUES (?, ?, ?, ?)""",
            (username.strip(), _hash_password(password), full_name.strip(), role),
        )


def list_users() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, username, full_name, role FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def update_user_role(user_id: int, role: str) -> None:
    if role not in ("cashier", "admin"):
        raise ValueError("role must be 'cashier' or 'admin'")
    with connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def update_user_password(user_id: int, password: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash_password(password), user_id),
        )


def delete_user(user_id: int) -> None:
    """Delete a user. The last remaining admin cannot be removed."""
    with connect() as conn:
        admins = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]
        target = conn.execute(
            "SELECT role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if target is not None and target["role"] == "admin" and admins <= 1:
            raise ValueError("Cannot delete the last admin account")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# --- products / inventory -----------------------------------------------------

def list_products() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, price, stock, cost_price FROM products ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(r) for r in rows]


def get_product(product_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, price, stock, cost_price FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    return dict(row) if row else None


def add_product(name: str, price: float, stock: int, cost_price: float = 0.0) -> int:
    if price < 0 or stock < 0 or cost_price < 0:
        raise ValueError("Price, stock, and cost price must be non-negative")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, price, stock, cost_price) VALUES (?, ?, ?, ?)",
            (name.strip(), price, stock, cost_price),
        )
        return cur.lastrowid


def update_product(product_id: int, name: str, price: float, stock: int, cost_price: float = 0.0) -> None:
    if price < 0 or stock < 0 or cost_price < 0:
        raise ValueError("Price, stock, and cost price must be non-negative")
    with connect() as conn:
        conn.execute(
            "UPDATE products SET name = ?, price = ?, stock = ?, cost_price = ? WHERE id = ?",
            (name.strip(), price, stock, cost_price, product_id),
        )


def delete_product(product_id: int) -> None:
    """Delete a product. Any bill_items referencing it get product_id NULL'd."""
    with connect() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


def deduct_stock(items: list[LineItem]) -> None:
    """Deduct quantities from product stock for every item tied to a product."""
    with connect() as conn:
        for item in items:
            if item.product_id is None:
                continue
            conn.execute(
                """UPDATE products SET stock = MAX(0, stock - ?)
                   WHERE id = ?""",
                (item.qty, item.product_id),
            )


def check_stock(items: list[LineItem]) -> dict[str, int]:
    """Return {product_name: available} for any product with insufficient stock."""
    short: dict[str, int] = {}
    with connect() as conn:
        for item in items:
            if item.product_id is None:
                continue
            row = conn.execute(
                "SELECT name, stock FROM products WHERE id = ?", (item.product_id,)
            ).fetchone()
            if row is None:
                continue
            if item.qty > row["stock"]:
                short[row["name"]] = row["stock"]
    return short


# --- customers / loyalty ------------------------------------------------------

def find_customer_by_phone(phone: str) -> dict | None:
    phone = (phone or "").strip()
    if not phone:
        return None
    with connect() as conn:
        row = conn.execute(
            """SELECT id, name, phone, email, loyalty_balance, created_at
               FROM customers WHERE phone = ? ORDER BY id LIMIT 1""",
            (phone,),
        ).fetchone()
    return dict(row) if row else None


def find_customer_by_name(name: str) -> dict | None:
    name = (name or "").strip()
    if not name:
        return None
    with connect() as conn:
        row = conn.execute(
            """SELECT id, name, phone, email, loyalty_balance, created_at
               FROM customers WHERE name = ? COLLATE NOCASE
               ORDER BY id LIMIT 1""",
            (name,),
        ).fetchone()
    return dict(row) if row else None


def get_or_create_customer(
    *, name: str, phone: str, email: str
) -> dict:
    """Reuse an existing customer (by phone, then name) or create a new one."""
    existing = find_customer_by_phone(phone) if phone else None
    if existing is None:
        existing = find_customer_by_name(name) if name else None
    if existing is not None:
        # Refresh contact details if the cashier entered something newer.
        new_name = name.strip() or existing["name"]
        new_email = (email or "").strip() or (existing["email"] or "")
        with connect() as conn:
            conn.execute(
                "UPDATE customers SET name = ?, email = ? WHERE id = ?",
                (new_name, new_email, existing["id"]),
            )
        return {**existing, "name": new_name, "email": new_email}
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, email, created_at) VALUES (?, ?, ?, ?)",
            (name.strip(), phone.strip(), email.strip(),
             datetime.now().isoformat(timespec="seconds")),
        )
        return {
            "id": cur.lastrowid,
            "name": name.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "loyalty_balance": 0,
        }


def list_customers(name: str = "", phone: str = "") -> list[dict]:
    q = "SELECT id, name, phone, email, loyalty_balance, created_at FROM customers WHERE 1=1"
    args: list = []
    if name.strip():
        q += " AND name LIKE ? COLLATE NOCASE"
        args.append(f"%{name.strip()}%")
    if phone.strip():
        q += " AND phone LIKE ?"
        args.append(f"%{phone.strip()}%")
    q += " ORDER BY name COLLATE NOCASE LIMIT 500"
    with connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def adjust_loyalty_balance(customer_id: int, delta: int) -> None:
    """Apply *delta* (positive earns, negative spends) to a customer balance."""
    with connect() as conn:
        conn.execute(
            """UPDATE customers
               SET loyalty_balance = MAX(0, loyalty_balance + ?)
               WHERE id = ?""",
            (delta, customer_id),
        )


# --- bills --------------------------------------------------------------------

def save_bill(bill: Bill, user_id: int | None = None) -> int:
    """Persist a finalized bill.

    Reuses/creates the customer, deducts inventory and updates the customer's
    loyalty balance (spent points minus points earned). Returns the new bill id.
    """
    customer = get_or_create_customer(
        name=bill.customer_name, phone=bill.customer_phone, email=bill.customer_email
    )
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO bills
               (customer_id, subtotal, discount, points_used, points_redeemed,
                tax, loyalty_points, total, payment_method, created_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                customer["id"],
                bill.subtotal,
                bill.discount,
                bill.points_used,
                bill.points_redeemed,
                bill.tax,
                bill.loyalty_points,
                bill.total,
                bill.payment_method,
                bill.created_at.isoformat(timespec="seconds"),
                user_id,
            ),
        )
        bill_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO bill_items
               (bill_id, product_id, description, qty, unit_price, line_total, unit_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (bill_id, it.product_id, it.description, it.qty, it.unit_price,
                 it.line_total, getattr(it, 'unit_cost', 0.0))
                for it in bill.items
            ],
        )
        conn.execute(
            """UPDATE customers
               SET loyalty_balance = MAX(0, loyalty_balance - ? + ?)
               WHERE id = ?""",
            (bill.points_used, bill.loyalty_points, customer["id"]),
        )
    deduct_stock(bill.items)
    return bill_id


def list_bills(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT b.id, b.created_at, b.total, b.loyalty_points, b.payment_method,
                      c.name AS customer_name, c.phone AS phone
               FROM bills b
               JOIN customers c ON c.id = b.customer_id
               ORDER BY b.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def search_bills(
    *,
    from_date: str = "",
    to_date: str = "",
    customer_name: str = "",
    phone: str = "",
    limit: int = 1000,
) -> list[dict]:
    """Bill-history search filterable by date range, customer name or phone."""
    q = (
        """SELECT b.id, b.created_at, b.subtotal, b.discount, b.tax,
                  b.loyalty_points, b.total, b.payment_method, c.name AS customer_name,
                  c.phone AS phone
           FROM bills b
           JOIN customers c ON c.id = b.customer_id
           WHERE 1=1"""
    )
    args: list = []
    if from_date:
        q += " AND substr(b.created_at, 1, 10) >= ?"
        args.append(from_date)
    if to_date:
        q += " AND substr(b.created_at, 1, 10) <= ?"
        args.append(to_date)
    if customer_name.strip():
        q += " AND c.name LIKE ? COLLATE NOCASE"
        args.append(f"%{customer_name.strip()}%")
    if phone.strip():
        q += " AND c.phone LIKE ?"
        args.append(f"%{phone.strip()}%")
    q += " ORDER BY b.id DESC LIMIT ?"
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def get_bill(bill_id: int) -> dict | None:
    """Return a bill header joined with its customer, or None."""
    with connect() as conn:
        row = conn.execute(
            """SELECT b.*, c.name AS customer_name, c.phone AS phone,
                      c.email AS email, c.loyalty_balance AS loyalty_balance
               FROM bills b JOIN customers c ON c.id = b.customer_id
               WHERE b.id = ?""",
            (bill_id,),
        ).fetchone()
    return dict(row) if row else None


def get_bill_items(bill_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM bill_items WHERE bill_id = ? ORDER BY id", (bill_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def refund_bill(bill_id: int) -> tuple[bool, str]:
    """Process a return/refund: restocks products and adjusts customer loyalty."""
    bill = get_bill(bill_id)
    if not bill:
        return False, "Bill not found"

    items = get_bill_items(bill_id)
    with connect() as conn:
        # Check if already refunded
        if "Refunded" in str(bill.get("payment_method", "")):
            return False, "This bill has already been refunded"

        # 1. Restock products
        for it in items:
            pid = it.get("product_id")
            qty = it.get("qty", 0)
            if pid and qty > 0:
                conn.execute(
                    "UPDATE products SET stock = stock + ? WHERE id = ?",
                    (qty, pid),
                )

        # 2. Adjust loyalty balance (reverse earned points)
        earned_pts = bill.get("loyalty_points", 0)
        cust_id = bill.get("customer_id")
        if cust_id and earned_pts > 0:
            conn.execute(
                "UPDATE customers SET loyalty_balance = MAX(0, loyalty_balance - ?) WHERE id = ?",
                (earned_pts, cust_id),
            )

        # 3. Mark bill payment method as Refunded
        conn.execute(
            "UPDATE bills SET payment_method = payment_method || ' (Refunded)' WHERE id = ?",
            (bill_id,),
        )

    return True, f"Bill #{bill_id} refunded successfully! Items restocked to inventory."


def bill_to_receipt(record: dict, items: list[dict]) -> Bill:
    """Reconstruct a :class:`Bill` from saved rows for receipt display."""
    return Bill(
        customer_id=record["customer_id"],
        customer_name=record.get("customer_name") or record.get("customer", ""),
        customer_phone=record.get("phone") or "",
        customer_email=record.get("email") or "",
        items=[
            LineItem(
                description=r["description"],
                qty=r["qty"],
                unit_price=r["unit_price"],
                product_id=r.get("product_id"),
            )
            for r in items
        ],
        subtotal=record["subtotal"],
        discount=record["discount"],
        points_used=record.get("points_used", 0),
        points_redeemed=record.get("points_redeemed", 0.0),
        tax=record["tax"],
        loyalty_points=record["loyalty_points"],
        total=record["total"],
        payment_method=record.get("payment_method", "Cash"),
        created_at=datetime.fromisoformat(record["created_at"]),
    )


def flatten_bill_items() -> list[dict]:
    """Every saved line item joined with its bill + customer, for CSV export."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT b.id AS bill_id, b.created_at, b.total AS bill_total,
                      c.name AS customer_name, c.phone AS phone,
                      bi.description, bi.qty, bi.unit_price, bi.line_total
               FROM bill_items bi
               JOIN bills b ON b.id = bi.bill_id
               JOIN customers c ON c.id = b.customer_id
               ORDER BY b.id DESC, bi.id"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_low_stock_products(threshold: int = 5) -> list[dict]:
    """Return products where stock is less than or equal to the threshold."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT name, stock, min_stock FROM products WHERE stock <= min_stock",
        ).fetchall()
    return [dict(r) for r in rows]

def _day_start() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def revenue_for_period(days: int) -> tuple[float, int, int]:
    """Return (total revenue, bill count, line items sold) over the last *days*."""
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    with connect() as conn:
        rev = conn.execute(
            "SELECT COALESCE(SUM(total), 0) FROM bills WHERE substr(created_at,1,10) >= ?",
            (start,),
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM bills WHERE substr(created_at,1,10) >= ?",
            (start,),
        ).fetchone()[0]
        sold = conn.execute(
            """SELECT COALESCE(SUM(qty), 0) FROM bill_items bi
               JOIN bills b ON b.id = bi.bill_id
               WHERE substr(b.created_at,1,10) >= ?""",
            (start,),
        ).fetchone()[0]
    return float(rev), count, sold


def revenue_series(days: int = 30) -> list[tuple[str, float]]:
    """Daily revenue for the last *days* days as [(date, total), ...]."""
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    with connect() as conn:
        rows = conn.execute(
            """SELECT substr(created_at,1,10) AS day, COALESCE(SUM(total), 0) AS rev
               FROM bills WHERE substr(created_at,1,10) >= ?
               GROUP BY day ORDER BY day""",
            (start,),
        ).fetchall()
    by_day = {r["day"]: r["rev"] for r in rows}
    series: list[tuple[str, float]] = []
    for offset in range(days):
        day = (datetime.now() - timedelta(days=days - 1 - offset)).strftime("%Y-%m-%d")
        series.append((day, float(by_day.get(day, 0.0))))
    return series


def top_items(limit: int = 5) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT description, SUM(qty) AS qty, SUM(line_total) AS revenue
               FROM bill_items GROUP BY description
               ORDER BY qty DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def top_customers(limit: int = 5) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.name AS customer_name, c.phone AS phone,
                      COUNT(b.id) AS bills, SUM(b.total) AS revenue
               FROM bills b JOIN customers c ON c.id = b.customer_id
               GROUP BY c.id ORDER BY revenue DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def revenue_by_payment_method(start_date: str = "", end_date: str = "") -> list[dict]:
    q = "SELECT payment_method, COALESCE(SUM(total), 0) as total, COUNT(id) as count FROM bills WHERE 1=1"
    args = []
    if start_date:
        q += " AND substr(created_at, 1, 10) >= ?"
        args.append(start_date)
    if end_date:
        q += " AND substr(created_at, 1, 10) <= ?"
        args.append(end_date)
    q += " GROUP BY payment_method"
    with connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def cashier_performance(start_date: str = "", end_date: str = "") -> list[dict]:
    q = """SELECT u.username, u.full_name, COALESCE(SUM(b.total), 0) as revenue, COUNT(b.id) as bills_count
           FROM bills b JOIN users u ON b.user_id = u.id WHERE 1=1"""
    args = []
    if start_date:
        q += " AND substr(b.created_at, 1, 10) >= ?"
        args.append(start_date)
    if end_date:
        q += " AND substr(b.created_at, 1, 10) <= ?"
        args.append(end_date)
    q += " GROUP BY u.id ORDER BY revenue DESC"
    with connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def profit_margins(start_date: str = "", end_date: str = "") -> tuple[float, float, float]:
    """Returns (total_revenue, total_cost, total_profit)."""
    q = """SELECT COALESCE(SUM(bi.line_total), 0) as revenue, 
                  COALESCE(SUM(bi.unit_cost * bi.qty), 0) as cost
           FROM bill_items bi JOIN bills b ON bi.bill_id = b.id WHERE 1=1"""
    args = []
    if start_date:
        q += " AND substr(b.created_at, 1, 10) >= ?"
        args.append(start_date)
    if end_date:
        q += " AND substr(b.created_at, 1, 10) <= ?"
        args.append(end_date)
    with connect() as conn:
        row = conn.execute(q, args).fetchone()
    
    rev = row["revenue"] if row and row["revenue"] else 0.0
    cost = row["cost"] if row and row["cost"] else 0.0
    return (float(rev), float(cost), float(rev - cost))


def revenue_for_period_custom(start_date: str = "", end_date: str = "") -> tuple[float, int, int]:
    q1 = "SELECT COALESCE(SUM(total), 0) FROM bills WHERE 1=1"
    q2 = "SELECT COUNT(*) FROM bills WHERE 1=1"
    q3 = "SELECT COALESCE(SUM(bi.qty), 0) FROM bill_items bi JOIN bills b ON b.id = bi.bill_id WHERE 1=1"
    args = []
    
    if start_date:
        cond = " AND substr(created_at,1,10) >= ?"
        cond_b = " AND substr(b.created_at,1,10) >= ?"
        q1 += cond; q2 += cond; q3 += cond_b
        args.append(start_date)
    if end_date:
        cond = " AND substr(created_at,1,10) <= ?"
        cond_b = " AND substr(b.created_at,1,10) <= ?"
        q1 += cond; q2 += cond; q3 += cond_b
        args.append(end_date)
        
    with connect() as conn:
        rev = conn.execute(q1, args).fetchone()[0]
        count = conn.execute(q2, args).fetchone()[0]
        sold = conn.execute(q3, args).fetchone()[0]
    return float(rev), count, sold
