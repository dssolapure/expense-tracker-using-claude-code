# Spec: Registration

## Overview
Registration allows a new visitor to create a Spendly account by submitting their full name, email address, and password. The server validates the input, hashes the password with werkzeug, inserts the new user into the `users` table, and redirects to the login page on success. On any failure (blank field, password too short, duplicate email) the form is re-rendered with a specific error message. This is the entry point for all authenticated features in the roadmap and must be in place before session management (Step 3) can be built.

## Depends on
- Step 1 — Database setup: `users` table created by `init_db()`, `get_db()` available

## Routes
- `POST /register` — process registration form submission — public

## Database changes
No database changes. The `users` table (`id`, `name`, `email` UNIQUE NOT NULL, `password_hash`, `created_at`) is already created by `init_db()` in Step 1.

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — already contains the POST form and `{% if error %}` block; no changes needed

## Files to change
- `app.py` — add `POST` to the route's `methods`; add `request`, `redirect`, `url_for`, `abort` to Flask imports; add `create_user` to db imports; add `generate_password_hash` import from werkzeug; implement POST branch logic
- `database/db.py` — add `create_user(name, email, password_hash)` helper after `seed_db()`

## Files to create
- `tests/__init__.py` — empty package marker
- `tests/conftest.py` — pytest app and client fixtures with isolated temp-file DB
- `tests/test_registration.py` — full test suite (15 tests)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` in `app.py` — never stored plain-text, never hashed inside `create_user()`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `create_user()` must live in `database/db.py` — no DB logic in `app.py`
- Catch `sqlite3.IntegrityError` in `create_user()` for duplicate email — return `None`, do not re-raise
- Close the DB connection in the `except` branch before returning `None` (prevent connection leaks)
- Use `abort(500)` for unexpected errors, not bare string returns

## Definition of done
- [ ] `POST /register` with valid name / email / password creates a row in `users` and returns a 302 redirect to `/login`
- [ ] The stored `password_hash` value is not equal to the submitted plain-text password
- [ ] Submitting a duplicate email re-renders the form (200) with the message "An account with that email already exists."
- [ ] Submitting a password shorter than 8 characters re-renders the form (200) with an error message containing "at least 8 characters"
- [ ] Submitting with a blank name re-renders the form (200) with the message "Name is required."
- [ ] `create_user()` returns `None` (without raising) when the email already exists
- [ ] All 15 tests in `tests/test_registration.py` pass with `pytest`