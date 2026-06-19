# Spec: Add Expense

## Overview
This feature lets a logged-in user submit a new expense via a form. It implements
the stub route `GET /expenses/add` (show the form) and adds `POST /expenses/add`
to handle submission. The expense is inserted into the existing `expenses` table,
which was created in Step 05. After a successful save the user is redirected to
their profile page so they can immediately see the new entry in the list.

## Depends on
- Step 02 — Registration (users table exists)
- Step 03 — Login / Logout (session management)
- Step 04 — Profile (redirect destination after save)
- Step 05 — Fetch data from DB to profile (expenses table and DB helpers exist)

## Routes
- `GET  /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the expense, redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

A new DB helper `add_expense(user_id, amount, category, date, description)` must be
added to `database/db.py`. It inserts one row and returns the new expense `id`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category (dropdown), date, description (optional)
- **Modify:** `templates/profile.html` — add an "Add Expense" button/link that points to `url_for('add_expense')`

## Files to change
- `app.py` — replace the stub `add_expense` route with GET+POST implementation; import `add_expense` from `database/db.py`
- `database/db.py` — add `add_expense()` helper
- `templates/profile.html` — add "Add Expense" link/button

## Files to create
- `templates/add_expense.html` — the expense entry form
- `static/css/add_expense.css` — page-specific styles (no inline `<style>` tags)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` with `get_db()` only
- Parameterised queries only — never use f-strings or `.format()` in SQL
- Passwords hashed with werkzeug (not relevant here, but mentioned for completeness)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Both GET and POST must redirect unauthenticated users to `/login`
- Amount must be a positive number (> 0); reject zero or negative values
- Date must match `YYYY-MM-DD` format; use the existing `_DATE_RE` regex in `app.py`
- Category must be one of the allowed values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- Description is optional (may be blank); store `None` if empty
- After a successful POST, redirect to `url_for('profile')` — do not re-render the form
- On validation failure, re-render the form with the error message and the user's previously entered values preserved
- Amount is stored as `REAL` in INR (₹); no currency conversion needed
- The allowed category list must be defined once in `app.py` and passed to the template — never hardcoded in HTML

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders the form
- [ ] Submitting the form with all valid fields inserts a row in `expenses` and redirects to `/profile`
- [ ] The new expense appears at the top of the expense list on the profile page
- [ ] Submitting with a blank amount shows a validation error and preserves other field values
- [ ] Submitting with amount = 0 or a negative number shows a validation error
- [ ] Submitting with an invalid date format shows a validation error
- [ ] Submitting with a category not in the allowed list shows a validation error
- [ ] Description is optional — the form submits successfully when description is left blank
- [ ] The "Add Expense" link on the profile page navigates to `/expenses/add`
- [ ] All form links and actions use `url_for()` — no hardcoded URLs
