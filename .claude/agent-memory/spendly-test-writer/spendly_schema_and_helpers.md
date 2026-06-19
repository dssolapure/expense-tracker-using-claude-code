---
name: Spendly DB Schema and Helper Functions
description: SQLite schema, available db.py helpers, session keys, and flash message strings discovered from reading the live codebase
type: project
---

## DB Schema

**users table**
- id (INTEGER PK AUTOINCREMENT)
- name (TEXT NOT NULL)
- email (TEXT UNIQUE NOT NULL)
- password_hash (TEXT NOT NULL)
- created_at (TEXT DEFAULT datetime('now'))  — format: "YYYY-MM-DD HH:MM:SS"

**expenses table**
- id (INTEGER PK AUTOINCREMENT)
- user_id (INTEGER NOT NULL, FK → users.id)
- amount (REAL NOT NULL)
- category (TEXT NOT NULL)
- date (TEXT NOT NULL)  — stored as "YYYY-MM-DD"
- description (TEXT)
- created_at (TEXT DEFAULT datetime('now'))

FK enforcement: PRAGMA foreign_keys = ON is applied on every `get_db()` call.

## DB Helpers (database/db.py)

- `get_db()` — opens sqlite3 connection, sets row_factory, applies FK pragma; uses `DB_PATH` module-level var (patchable in tests via `db_module.DB_PATH = db_path`)
- `init_db()` — creates users and expenses tables if not exists
- `seed_db()` — inserts Demo User + 8 seed expenses only if users table is empty
- `create_user(name, email, password_hash)` — returns int user_id or None on IntegrityError (duplicate email)
- `get_user_by_email(email)` — returns sqlite3.Row or None
- `get_user_by_id(user_id)` — returns sqlite3.Row or None
- `get_user_expenses(user_id, from_date=None, to_date=None)` — returns list of dicts with keys: date (formatted), description, category, amount (₹-formatted); capped at 10 rows
- `get_user_stats(user_id, from_date=None, to_date=None)` — returns dict: {total_spent, transaction_count, top_category}; total_spent="₹0", top_category="—" when no expenses
- `get_user_categories(user_id, from_date=None, to_date=None)` — returns list of dicts: {name, total, pct}; capped at 7 categories; returns [] when grand_total==0
- `_fmt_member_since(created_at_str)` — parses "%Y-%m-%d %H:%M:%S", returns "%B %Y"
- `_fmt_amount(amount_float)` — returns "₹{int:,}" (rupee symbol + comma thousands)
- `_fmt_date(date_str)` — parses "%Y-%m-%d", returns e.g. "15 Jun 2026"

## Session Keys

- `session["user_id"]` — integer; set on successful login, cleared on logout
- `session.get("user_id")` is the auth guard pattern in all protected routes

## Flash Message / Error Strings

Login route:
- "Email is required."
- "Password is required."
- "Invalid email or password."

Register route:
- "Name is required."
- "Email is required."
- "Password is required."
- "Password must be at least 8 characters."
- "An account with that email already exists."

Profile / date-filter route:
- "Please provide both a start and an end date."  (hint — only one date given)
- "Start date must be on or before the end date."  (error — from > to)
- "Invalid start date. Use YYYY-MM-DD format."  (error — from_date fails _DATE_RE)
- "Invalid end date. Use YYYY-MM-DD format."    (error — to_date fails _DATE_RE)

Date-filter validation order in /profile route:
1. Malformed from_date → filter_error, both reset to ""
2. Malformed to_date → filter_error, both reset to ""
3. Only one of the two provided → filter_hint, both reset to "" (filter inactive)
4. Both provided, from > to → filter_error, both reset to "" (filter inactive)
5. Both provided, from <= to → active_filter=True, helpers called with date args

`get_user_expenses` when filter active: no LIMIT 10 applied (all matching rows returned).
`get_user_expenses` without filter: LIMIT 10 applied (most-recent 10 rows).

`_fmt_date` uses `%#d` on Windows (no zero-padding) — use "Jun 2026" substring checks
rather than "01 Jun 2026" to stay platform-portable in active-badge tests.

## Route Behaviours

- Login success redirects to `/profile`
- Logout redirects to `/` (landing)
- Profile auth guard: checks `session.get("user_id")`; missing → redirect `/login`; user not in DB → session.clear() + redirect `/login`
- Date filter: `from_date` and `to_date` as query params on GET /profile; mismatched (one only) → hint + treat as inactive; from > to → error + treat as inactive; both valid → `active_filter=True` + filter all three data sections

**Why:** Captured once from live codebase so future test sessions don't need to re-read every file.
**How to apply:** Use these strings literally in `assert b"..." in response.data` checks.
