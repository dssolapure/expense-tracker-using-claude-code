import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "spendly.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    expenses = [
        (user_id, 320.00,  "Food",          "2026-06-01", "Lunch at Darshini"),
        (user_id, 850.00,  "Transport",     "2026-06-03", "Monthly bus pass"),
        (user_id, 2500.00, "Bills",         "2026-06-05", "Electricity bill"),
        (user_id, 180.00,  "Food",          "2026-06-07", "Evening snacks"),
        (user_id, 600.00,  "Health",        "2026-06-09", "Pharmacy — vitamins"),
        (user_id, 499.00,  "Entertainment", "2026-06-11", "OTT subscription"),
        (user_id, 1350.00, "Shopping",      "2026-06-13", "Clothing — kurta set"),
        (user_id, 75.00,   "Other",         "2026-06-15", "Stationery — notebook"),
    ]
    cursor.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user


def create_user(name, email, password_hash):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def _fmt_amount(amount_float):
    return f"₹{int(amount_float):,}"


def _fmt_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%#d %b %Y")


def _fmt_member_since(created_at_str):
    dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%B %Y")


def _date_filter(from_date, to_date):
    if from_date and to_date:
        return " AND date BETWEEN ? AND ?", [from_date, to_date]
    return "", []


def get_user_expenses(user_id, from_date=None, to_date=None):
    conn = get_db()
    cursor = conn.cursor()
    date_clause, date_params = _date_filter(from_date, to_date)
    sql = ("SELECT date, description, category, amount FROM expenses "
           "WHERE user_id = ?" + date_clause)
    params = [user_id] + date_params
    sql += " ORDER BY date DESC" if date_clause else " ORDER BY date DESC LIMIT 10"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "date": _fmt_date(row["date"]),
            "description": row["description"],
            "category": row["category"],
            "amount": _fmt_amount(row["amount"]),
        }
        for row in rows
    ]


def get_user_stats(user_id, from_date=None, to_date=None):
    conn = get_db()
    cursor = conn.cursor()
    date_clause, date_params = _date_filter(from_date, to_date)

    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
        "FROM expenses WHERE user_id = ?" + date_clause,
        [user_id] + date_params,
    )
    row = cursor.fetchone()
    total_float, count = row["total"], row["cnt"]
    cursor.execute(
        "SELECT category, SUM(amount) AS cat_total FROM expenses "
        "WHERE user_id = ?" + date_clause +
        " GROUP BY category ORDER BY cat_total DESC LIMIT 1",
        [user_id] + date_params,
    )
    top_row = cursor.fetchone()
    conn.close()
    return {
        "total_spent": _fmt_amount(total_float) if count > 0 else "₹0",
        "transaction_count": count,
        "top_category": top_row["category"] if top_row else "—",
    }


def get_user_categories(user_id, from_date=None, to_date=None):
    conn = get_db()
    cursor = conn.cursor()
    date_clause, date_params = _date_filter(from_date, to_date)

    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS grand_total FROM expenses "
        "WHERE user_id = ?" + date_clause,
        [user_id] + date_params,
    )
    grand_total = cursor.fetchone()["grand_total"]
    if grand_total == 0:
        conn.close()
        return []
    cursor.execute(
        "SELECT category, SUM(amount) AS cat_total FROM expenses "
        "WHERE user_id = ?" + date_clause +
        " GROUP BY category ORDER BY cat_total DESC LIMIT 7",
        [user_id] + date_params,
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "name": row["category"],
            "total": _fmt_amount(row["cat_total"]),
            "pct": round(row["cat_total"] / grand_total * 100),
        }
        for row in rows
    ]
