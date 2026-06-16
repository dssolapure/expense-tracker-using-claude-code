# Plan: Database Setup (Step 1)

## Context

`database/db.py` is currently a stub with only comments. No DB exists. All future steps (auth, expenses, profile) depend on this being correctly implemented first. The goal is to implement the three required helper functions and wire them into `app.py` startup.

---

## Files to Change

| File | Change |
|---|---|
| `database/db.py` | Implement `get_db()`, `init_db()`, `seed_db()` from scratch |
| `app.py` | Add import + startup wiring with `app.app_context()` |

---

## Implementation

### `database/db.py`

```python
import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "spendly.db")


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
```

### `app.py` — two changes only

1. Add import after existing import line:
```python
from database.db import get_db, init_db, seed_db
```

2. Add startup block immediately after `app = Flask(__name__)`:
```python
with app.app_context():
    init_db()
    seed_db()
```

---

## Key Decisions

- **`DB_PATH` via `os.path.abspath(__file__)`** — anchors `spendly.db` to project root regardless of working directory
- **`PRAGMA foreign_keys = ON` in `get_db()`** — SQLite resets FK enforcement per connection; must be in the factory
- **`DEFAULT (datetime('now'))` with parentheses** — without parens, SQLite stores it as a literal string, not a function call
- **`seed_db()` guard: `SELECT COUNT(*) FROM users`** — cheapest duplicate prevention; returns early if any user exists
- **`cursor.lastrowid`** — captures demo user's auto-generated id instead of hardcoding `1`
- **INR amounts** — all sample amounts use realistic Indian household figures (₹75–₹2500)
- All 7 categories covered; Food appears twice (realistic), dates span June 2026

---

## Verification

1. Run `python app.py` — server starts on port 5001, no errors
2. Verify `spendly.db` is created in project root
3. Open DB with sqlite3 CLI or DB Browser:
   - `SELECT * FROM users;` → 1 row, hashed password
   - `SELECT * FROM expenses;` → 8 rows across 7 categories
4. Restart `python app.py` — verify `seed_db()` does not duplicate rows (still 1 user, 8 expenses)
5. Test FK enforcement: attempt to insert an expense with a non-existent `user_id` — should raise `IntegrityError`
