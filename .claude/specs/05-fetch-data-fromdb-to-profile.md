# Spec: Fetch Data From DB To Profile

## Overview
Step 4 built a fully styled profile page rendered with hardcoded mock data. Step 5 replaces every hardcoded value with real database queries. When a logged-in user visits `/profile`, the app will look up their record in the `users` table, load their expenses from the `expenses` table, and compute aggregated stats (total spent, transaction count, top category) — all formatted for the ₹/INR locale before being passed to the template.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables exist)
- Step 2 — Registration (`create_user`, users can exist in the DB)
- Step 3 — Login/logout (`user_id` is stored in session on login)
- Step 4 — Profile UI (`/profile` route and `profile.html` template exist with the correct context keys)

## Routes
No new routes. The existing `GET /profile` route is modified to replace hardcoded context with live DB queries.

## Database changes
No schema changes. Two new helper functions are added to `database/db.py`:
- `get_user_by_id(user_id)` — returns the users row for the given id, or `None`
- `get_expenses_by_user(user_id)` — returns all expense rows for the user, ordered by `date DESC`

## Templates
- **Modify:** `templates/profile.html` — no structural changes needed; template already uses the correct context keys. Verify date and amount formatting matches what the route now supplies.

## Files to change
- `database/db.py` — add `get_user_by_id()` and `get_expenses_by_user()`
- `app.py` — rewrite the `/profile` route body to call the new helpers and build `user`, `stats`, `expenses`, and `categories` from real data
- `tests/test_profile.py` — update existing tests to insert real DB rows; add new tests that verify live data is rendered

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw sqlite3 only
- Parameterised queries only — never f-strings in SQL
- `get_db()` must already set `PRAGMA foreign_keys = ON` and `row_factory = sqlite3.Row` (already done in Step 1)
- All templates extend `base.html` — do not alter the template inheritance
- Use CSS variables — never hardcode hex values
- Passwords hashed with werkzeug (no changes needed here)
- If `get_user_by_id()` returns `None` (stale/invalid session), clear the session and `abort(401)` or redirect to `/login`
- Date formatting: DB stores `YYYY-MM-DD`; template expects human-readable form (e.g. `"15 Jun 2026"`) — format in Python, not in Jinja
- Amount formatting: template expects `"₹X,XXX"` strings — build a small formatting helper or inline it in the route, not in SQL
- `stats["total_spent"]` — sum of all `amount` values for the user; `0` if no expenses
- `stats["top_category"]` — category with the highest total spend; `"—"` if no expenses
- `categories` list — group expenses by category, compute per-category total and percentage of overall spend, sorted descending by total; limit to top 7
- `expenses` list passed to template — all user expenses, ordered by date descending; limit to most recent 10 for the Recent Transactions panel

## Definition of done
- [ ] Visiting `/profile` while logged in shows the logged-in user's actual name and email (not hardcoded values)
- [ ] `member_since` reflects the user's real `created_at` date from the DB
- [ ] Total spent stat matches the sum of that user's expense rows in the DB
- [ ] Transaction count stat matches the number of expense rows for that user
- [ ] Top category stat is derived from real expense data
- [ ] Recent Transactions panel lists actual expense rows (date, description, category, amount)
- [ ] Category breakdown reflects real per-category aggregation with correct percentages
- [ ] A user with zero expenses sees `₹0` for total, `0` for count, `"—"` for top category, and empty lists
- [ ] A stale session (user_id not in DB) redirects to `/login` (does not crash)
- [ ] All existing `pytest` tests in `tests/test_profile.py` pass with real DB data
