# Spec: Delete Functionality

## Overview
This feature lets a logged-in user delete one of their own expense records. It
replaces the stub `GET /expenses/<id>/delete` with a `POST`-only handler (deleting
data must not happen via GET). A small HTML form in the Actions column of the profile
expense table submits a POST request; the route deletes the row and redirects back to
the profile page. Ownership is enforced — unrecognised ids return 404 and attempts
to delete another user's expense return 403.

## Depends on
- Step 02 — Registration (users table exists)
- Step 03 — Login / Logout (session management)
- Step 04 — Profile (redirect destination after delete)
- Step 05 — Fetch data from DB to profile (expenses table and DB helpers)
- Step 08 — Edit Expense (`get_expense_by_id` helper already exists; Actions column already in `profile.html`)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense row, redirect to `/profile` — logged-in only

> The stub is currently `GET`. It must be changed to `POST` only. Using GET for a
> destructive operation is unsafe — a browser prefetch or link crawler could trigger
> unintended deletions.

## Database changes
No new tables or columns. One new DB helper required:

- `delete_expense(expense_id)` — runs `DELETE FROM expenses WHERE id = ?`

`get_expense_by_id` (already exists from Step 08) is reused for the ownership check.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — add a Delete button in the existing Actions
  column alongside the Edit link; the button must be wrapped in a `<form>` with
  `method="POST"` and `action="{{ url_for('delete_expense', id=expense.id) }}"`

## Files to change
- `app.py` — replace stub `delete_expense` route with POST-only handler; import `delete_expense` from `database/db.py`
- `database/db.py` — add `delete_expense(expense_id)` helper
- `templates/profile.html` — add Delete form/button in Actions column per expense row
- `static/css/profile.css` — append styles for `.txn-delete-btn`

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` with `get_db()` only
- Parameterised queries only — never use f-strings or `.format()` in SQL
- Passwords hashed with werkzeug (not applicable here, stated for completeness)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Route must be `POST` only — do not accept `GET` for a delete operation
- Auth guard: redirect unauthenticated users to `/login`
- Reuse `get_expense_by_id` (already in `db.py`) for the ownership check
- Ownership check: `expense["user_id"] != session["user_id"]` → `abort(403)`
- Non-existent id → `abort(404)`
- After successful delete, redirect to `url_for('profile')` — never re-render inline
- The Delete button in `profile.html` must be a `<form>` with `method="POST"` —
  never a plain `<a>` link, as links issue GET requests
- No JavaScript confirm dialogs — the delete is immediate on POST

## Definition of done
- [ ] `POST /expenses/<id>/delete` while logged out redirects to `/login`
- [ ] `POST /expenses/999/delete` (non-existent id) returns 404
- [ ] `POST /expenses/<other-user-expense-id>/delete` returns 403
- [ ] `POST /expenses/<id>/delete` with valid ownership deletes the row and redirects to `/profile`
- [ ] The deleted expense no longer appears in the profile expense list
- [ ] Each expense row on the profile page has a working Delete button
- [ ] The Delete button submits via POST (not a plain link)
- [ ] Stats and category breakdown on the profile page update to reflect the deletion
- [ ] All form actions use `url_for()` — no hardcoded URLs
