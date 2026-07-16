# Spec: Edit Expense

## Overview
This feature lets a logged-in user edit an existing expense record. It replaces the
stub route `GET /expenses/<id>/edit` with a full GET+POST implementation. The GET
renders a pre-filled form with the expense's current values; the POST validates the
input, updates the row in the `expenses` table, and redirects to the profile page.
Ownership is enforced — a user may only edit their own expenses. Unrecognised expense
ids return 404; attempts to edit another user's expense return 403.

## Depends on
- Step 02 — Registration (users table exists)
- Step 03 — Login / Logout (session management)
- Step 04 — Profile (redirect destination after save)
- Step 05 — Fetch data from DB to profile (expenses table and DB helpers)
- Step 07 — Add Expense (EXPENSE_CATEGORIES list, validation rules, form/CSS patterns)

## Routes
- `GET  /expenses/<int:id>/edit` — render pre-filled edit form for the expense — logged-in only
- `POST /expenses/<int:id>/edit` — validate and update the expense row, redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. Two new DB helpers required in `database/db.py`:

- `get_expense_by_id(expense_id)` — fetches one expense row by id (all columns) or returns `None`
- `update_expense(expense_id, amount, category, date, description)` — updates the four editable columns for the given id

`get_user_expenses()` must also be modified to include `id` in its SELECT and return dict
so the profile template can build edit links per row.

## Templates
- **Create:** `templates/edit_expense.html` — pre-filled form with amount, category dropdown, date, description (optional); mirrors `add_expense.html` structure
- **Modify:** `templates/profile.html` — add an Actions column to the expense table with an Edit link per row pointing to `url_for('edit_expense', id=expense.id)`

## Files to change
- `app.py` — replace stub `edit_expense` route with GET+POST; add `methods=["GET", "POST"]`; import `get_expense_by_id` and `update_expense`
- `database/db.py` — add `get_expense_by_id()` and `update_expense()` helpers; update `get_user_expenses()` to select and return `id`
- `templates/profile.html` — add Actions column header and Edit link per expense row
- `static/css/profile.css` — append styles for `.txn-table__td--actions` and `.txn-edit-link`

## Files to create
- `templates/edit_expense.html` — the pre-filled edit form
- `static/css/edit_expense.css` — page-specific styles (no inline `<style>` tags)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` with `get_db()` only
- Parameterised queries only — never use f-strings or `.format()` in SQL
- Passwords hashed with werkzeug (not applicable here, stated for completeness)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Both GET and POST must redirect unauthenticated users to `/login`
- Ownership check: after fetching expense by id, verify `expense["user_id"] == session["user_id"]`; if mismatch call `abort(403)`
- If expense id does not exist, call `abort(404)`
- Amount must be a positive number (> 0); reject zero or negative values
- Date must match `YYYY-MM-DD` format; use the existing `_DATE_RE` regex in `app.py`
- The GET handler must pass the raw `YYYY-MM-DD` date string (from DB) into `form["date"]` — NOT the formatted display string — so the `<input type="date">` pre-fills correctly
- Category must be one of the values in `EXPENSE_CATEGORIES` defined in `app.py`
- Description is optional; store `None` if blank
- After a successful POST, redirect to `url_for('profile')` — do not re-render the form
- On validation failure, re-render the edit form with the error and the user's submitted values (not the original DB values)
- `get_user_expenses()` change must be backward-compatible — existing `expense.date`, `expense.description`, `expense.category`, `expense.amount` references in `profile.html` must continue to work

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/999/edit` (non-existent id) returns 404
- [ ] Visiting `/expenses/<id>/edit` for another user's expense returns 403
- [ ] Visiting `/expenses/<id>/edit` while logged in renders the form pre-filled with current expense values
- [ ] The date field is pre-filled in `YYYY-MM-DD` format and shows correctly in the browser date picker
- [ ] Submitting the form with all valid fields updates the row in `expenses` and redirects to `/profile`
- [ ] The updated values (including changed date) appear correctly in the expense list on the profile page
- [ ] Submitting with a blank amount shows a validation error and preserves other submitted values
- [ ] Submitting with amount = 0 or negative shows a validation error
- [ ] Submitting with an invalid date format shows a validation error
- [ ] Submitting with a category not in the allowed list shows a validation error
- [ ] Description is optional — the form submits successfully when description is left blank
- [ ] Each expense row on the profile page has a working Edit link
- [ ] All form actions and links use `url_for()` — no hardcoded URLs
