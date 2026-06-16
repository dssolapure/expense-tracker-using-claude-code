# Plan: Step 2 — Registration

## Context
Branch: `feature/registration` | Spec: `.claude/specs/02-registration.md`

`GET /register` renders a complete HTML form (name, email, password fields, `{% if error %}` block) but there is no `POST` handler. `database/db.py` has `get_db()`, `init_db()`, `seed_db()` — but no `create_user()`. The `users` table (id, name, email UNIQUE, password_hash, created_at) already exists. This plan adds the POST handler, the DB helper, and a full test suite. No templates or schema changes are needed.

---

## Critical files
| File | Action | Key change |
|---|---|---|
| `database/db.py` | Modify | Add `create_user()` after `seed_db()` |
| `app.py` | Modify | Extend `register()` to handle POST |
| `tests/__init__.py` | Create | Empty — makes tests/ a package |
| `tests/conftest.py` | Create | `app` + `client` fixtures, isolated temp DB |
| `tests/test_registration.py` | Create | 15 tests |

---

## Implementation order

### 1 — `database/db.py`: add `create_user(name, email, password_hash)`

Add after the closing of `seed_db()`. The function must:

- Open a connection via the existing `get_db()` (reuse, never inline `sqlite3.connect`)
- Execute a parameterized `INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)` with the three args as a tuple — no f-strings
- On success: `conn.commit()`, capture `cursor.lastrowid`, `conn.close()`, return the integer ID
- Wrap in `try/except sqlite3.IntegrityError` only (not broad `Exception`):
  - In the except block: `conn.close()` first, then `return None`
  - This handles the UNIQUE constraint on `email` without raising to the caller
- Do NOT call `generate_password_hash` here — accept the already-hashed string as an argument

Also add `create_user` to the export (the import line in `app.py`).

---

### 2 — `app.py`: extend `register()` for POST

**Import line changes (two lines at top):**
- `from flask import Flask, render_template` → add `request, redirect, url_for, abort`
- `from database.db import get_db, init_db, seed_db` → add `create_user`
- Add new line: `from werkzeug.security import generate_password_hash`

**Route decorator:**
`@app.route("/register")` → `@app.route("/register", methods=["GET", "POST"])`

**Function body — GET branch:**
`if request.method == "GET": return render_template("register.html")` — unchanged behaviour

**Function body — POST branch, in strict order:**

Step 1 — Read form data:
- `name = request.form.get("name", "").strip()`
- `email = request.form.get("email", "").strip()`
- `password = request.form.get("password", "")` ← no strip; whitespace in a password is intentional

Step 2 — Validate (fail-fast, stop at first failure):
- `not name` → `render_template("register.html", error="Name is required.")`
- `not email` → `render_template("register.html", error="Email is required.")`
- `not password` → `render_template("register.html", error="Password is required.")`
- `len(password) < 8` → `render_template("register.html", error="Password must be at least 8 characters.")`

Step 3 — Hash (only after all validation passes):
- `password_hash = generate_password_hash(password)`

Step 4 — Insert:
- `user_id = create_user(name, email, password_hash)` inside a `try/except Exception: abort(500)`
- `if user_id is None:` → `render_template("register.html", error="An account with that email already exists.")`
- `else:` → `redirect(url_for("login"))` (302 by default)

---

### 3 — `tests/__init__.py`

Empty file. Its sole purpose is making `tests/` a Python package so pytest can resolve imports correctly.

---

### 4 — `tests/conftest.py`

Two function-scoped pytest fixtures:

**`app` fixture:**
1. `fd, db_path = tempfile.mkstemp(suffix=".db")` then `os.close(fd)` — creates an isolated temp file
2. Save `original_path = db_module.DB_PATH`, then set `db_module.DB_PATH = db_path`
   - This patches the module-level variable before any `get_db()` call, so all DB operations in the test hit the temp file, not `spendly.db`
3. `flask_app.app.config["TESTING"] = True`
4. Push an app context, call `init_db()` (schema only — do NOT call `seed_db()`)
5. `yield flask_app.app`
6. Teardown: restore `db_module.DB_PATH = original_path`, delete temp file with `os.unlink(db_path)`

> File-backed DB (not `:memory:`) is required because `get_db()` opens a new `sqlite3.connect()` on each call; `:memory:` databases are connection-scoped and would appear empty to every second call.

**`client` fixture:**
- Depends on `app`
- Returns `app.test_client()`

---

### 5 — `tests/test_registration.py` — 15 tests

**GET tests (2)**

| Test | Action | Assert |
|---|---|---|
| `test_register_get_returns_200` | `GET /register` | status 200 |
| `test_register_get_renders_form` | `GET /register` | `b"Create your account"` in response.data |

**Happy-path POST tests (3)**

| Test | Action | Assert |
|---|---|---|
| `test_register_post_valid_redirects` | POST valid data, `follow_redirects=False` | status 302, Location ends with `/login` |
| `test_register_post_creates_user_in_db` | POST valid data, then query DB | row exists with correct name and email |
| `test_register_password_is_hashed` | POST valid data, then query DB | `row["password_hash"] != "secure123"` and `check_password_hash(hash, "secure123")` is `True` |

**Validation failure tests (6)**

| Test | Input | Assert |
|---|---|---|
| `test_register_blank_name` | `name=""` | 200, `b"Name is required"` in body |
| `test_register_blank_email` | `email=""` | 200, `b"Email is required"` in body |
| `test_register_blank_password` | `password=""` | 200, `b"Password is required"` in body |
| `test_register_short_password` | `password="abc"` | 200, `b"at least 8 characters"` in body |
| `test_register_password_7_chars_fails` | `password="1234567"` (boundary) | 200 (must fail) |
| `test_register_password_8_chars_succeeds` | `password="12345678"` (boundary) | 302 (must pass) |

**Duplicate email tests (2)**

| Test | Action | Assert |
|---|---|---|
| `test_register_duplicate_email` | Register same email twice | 200, `b"An account with that email already exists."` |
| `test_register_duplicate_no_second_row` | Register same email twice, query DB | `COUNT(*) == 1` |

**DB unit tests (2)**

| Test | Action | Assert |
|---|---|---|
| `test_create_user_returns_id` | Call `create_user()` directly | Returns `int > 0` |
| `test_create_user_duplicate_returns_none` | Call `create_user()` twice, same email | First returns `int`, second returns `None`, no exception raised |

---

## Risks to watch
- **Test DB isolation**: patch `database.db.DB_PATH` before any `get_db()` call — if missed, tests write to `spendly.db`
- **Connection leak on IntegrityError**: `create_user()` must `conn.close()` in the `except` branch before `return None`
- **Missing `methods` on decorator**: without `methods=["GET", "POST"]` Flask returns 405 on all POST requests silently
- **Hashing inside `create_user()`**: must not happen — function only accepts a pre-hashed string

---

## Verification
1. `python app.py` → visit `http://localhost:5001/register`, submit valid data → should land on `/login`
2. Submit duplicate email → form re-renders with "An account with that email already exists."
3. Submit `password="1234567"` (7 chars) → form re-renders with length error
4. `pytest tests/test_registration.py -v` → 15 passed
