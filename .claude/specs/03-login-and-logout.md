# Spec: Login and Logout

## Overview
Login and Logout introduces Flask session management to Spendly. A returning user submits their email and password via `POST /login`; the server looks up the account, verifies the password with werkzeug, and stores the user's `id` in the Flask session on success before redirecting to `/profile`. On any failure (blank field, unknown email, wrong password) the login form is re-rendered with a generic error message so as not to leak account existence. `GET /logout` clears the session and redirects to the landing page. The navigation bar in `base.html` is updated to show context-aware links: "Sign in" / "Get started" when anonymous, "Logout" when a session is active.

## Depends on
- Step 1 — Database setup: `users` table and `get_db()` available
- Step 2 — Registration: `users` rows exist to log in with

## Routes
- `POST /login` — process login form, verify credentials, write session — public
- `GET /logout` — clear session, redirect to landing — public (no auth guard needed)

## Database changes
No database changes. The `users` table already contains `id`, `email`, and `password_hash`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — fix hardcoded `action="/login"` → `action="{{ url_for('login') }}"`
  - `templates/base.html` — make nav links conditional: show "Sign in" + "Get started" when `session` has no `user_id`; show "Logout" linking to `url_for('logout')` when `user_id` is present

## Files to change
- `app.py` — set `app.secret_key`; add `POST` to `/login` methods, import `session` from Flask and `check_password_hash` from werkzeug, import `get_user_by_email` from db, implement POST branch; implement `GET /logout`
- `database/db.py` — add `get_user_by_email(email)` helper that returns a `sqlite3.Row` or `None`
- `templates/login.html` — fix hardcoded form action URL
- `templates/base.html` — conditional nav links based on `session.get('user_id')`

## Files to create
- `tests/test_login_logout.py` — full test suite

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already available via Flask's dependency.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `get_user_by_email()` must live in `database/db.py` — no DB logic in `app.py`
- `app.secret_key` must be set before any session use — use a fixed dev string (e.g. `"spendly-dev-secret"`) acceptable for this project stage
- On login failure, use the same generic message for both "unknown email" and "wrong password" — do not reveal which is wrong
- Store only `user_id` (integer) in the session — never store the full user row or password hash
- `GET /logout` must call `session.clear()`, not `session.pop('user_id')`, to wipe the full session
- Redirect after successful login goes to `url_for('profile')` (stub is fine at this stage)
- Use `abort()` for unexpected server errors, not bare string returns

## Definition of done
- [ ] `POST /login` with correct email + password creates a session containing `user_id` and returns a 302 redirect to `/profile`
- [ ] `POST /login` with an unknown email re-renders the form (200) with the error "Invalid email or password."
- [ ] `POST /login` with a correct email but wrong password re-renders the form (200) with the error "Invalid email or password."
- [ ] `POST /login` with a blank email or blank password re-renders the form (200) with an appropriate error message
- [ ] `GET /logout` clears the session and returns a 302 redirect to `/` (landing)
- [ ] After logout, visiting `/logout` again still redirects to `/` without error
- [ ] `base.html` nav shows "Sign in" and "Get started" when no session is active
- [ ] `base.html` nav shows "Logout" link when a session with `user_id` is active
- [ ] `login.html` form action uses `url_for('login')`, not a hardcoded string
- [ ] All tests in `tests/test_login_logout.py` pass with `pytest`
