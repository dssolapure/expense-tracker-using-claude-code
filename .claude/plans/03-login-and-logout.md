# Implementation Plan: Step 03 — Login and Logout

## Context
Spendly currently has no session management. The login route is GET-only and the logout route is a stub. This step wires up Flask sessions so users can authenticate with email+password and maintain a logged-in state. It is the prerequisite for all authenticated features (profile, expenses).

---

## Implementation Order

```
1. database/db.py        — add get_user_by_email()
2. app.py                — secret_key, imports, POST /login, GET /logout
3. templates/login.html  — fix hardcoded form action URL
4. templates/base.html   — conditional nav links based on session
5. tests/__init__.py     — empty package marker
6. tests/conftest.py     — isolated temp-DB fixtures
7. tests/test_login_logout.py — 13 tests
```

---

## File Changes

### 1. `database/db.py` — Add `get_user_by_email(email)`

Add after `seed_db()`:

```python
def get_user_by_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user
```

- Returns a `sqlite3.Row` (supports `row["id"]`, `row["password_hash"]`) or `None`
- No try/except needed — pure SELECT, no mutation risk

---

### 2. `app.py`

**Import line changes:**
```python
# Before
from flask import Flask, render_template, request, redirect, url_for, abort
from werkzeug.security import generate_password_hash
from database.db import get_db, init_db, seed_db, create_user

# After
from flask import Flask, render_template, request, redirect, url_for, abort, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
```

**Add `secret_key` immediately after `app = Flask(__name__)`:**
```python
app = Flask(__name__)
app.secret_key = "spendly-dev-secret"
```

**Replace `GET /login` with `GET+POST /login`:**
```python
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email:
        return render_template("login.html", error="Email is required.")
    if not password:
        return render_template("login.html", error="Password is required.")

    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))
```

**Replace `GET /logout` stub:**
```python
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))
```

**Design decisions:**
- Blank-field check before DB lookup: gives specific error ("Email is required.") vs. the generic credential error
- `user is None or not check_password_hash(...)` collapsed into one branch — same response for unknown email and wrong password (spec requirement, avoids leaking account existence)
- `session.clear()` before setting `user_id` — destroys any stale session data
- Store only `user["id"]` (integer) in session — never name, email, or hash
- `session.clear()` in logout (not `.pop()`) — spec explicit requirement

---

### 3. `templates/login.html` — Fix Hardcoded Action URL

Line 20, one-line change:
```html
<!-- Before -->
<form method="POST" action="/login">

<!-- After -->
<form method="POST" action="{{ url_for('login') }}">
```

---

### 4. `templates/base.html` — Conditional Nav Links

Replace the `<div class="nav-links">` block:
```html
<!-- Before -->
<div class="nav-links">
    <a href="{{ url_for('login') }}">Sign in</a>
    <a href="{{ url_for('register') }}" class="nav-cta">Get started</a>
</div>

<!-- After -->
<div class="nav-links">
    {% if session.get('user_id') %}
        <a href="{{ url_for('logout') }}">Logout</a>
    {% else %}
        <a href="{{ url_for('login') }}">Sign in</a>
        <a href="{{ url_for('register') }}" class="nav-cta">Get started</a>
    {% endif %}
</div>
```

- Use `session.get('user_id')` not `session['user_id']` — Jinja2 raises `UndefinedError` on missing key access; `.get()` returns `None` safely
- Flask makes `session` available in all templates automatically — no explicit pass needed

---

### 5. `tests/__init__.py` — Empty File

Create empty file. Makes `tests/` a Python package for pytest import resolution.

---

### 6. `tests/conftest.py` — Isolated Test Fixtures

```python
import os
import tempfile
import pytest

import app as flask_app
import database.db as db_module


@pytest.fixture()
def app():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_path

    flask_app.app.config["TESTING"] = True

    with flask_app.app.app_context():
        db_module.init_db()

    yield flask_app.app

    db_module.DB_PATH = original_path
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()
```

**Key design decisions:**
- `tempfile.mkstemp()` not `:memory:` — `get_db()` opens a new connection each call; `:memory:` DBs are connection-scoped so a second call would see an empty DB
- Monkey-patch `db_module.DB_PATH` directly — redirects all `get_db()` calls to temp file, never touches `spendly.db`
- `init_db()` only, NOT `seed_db()` — tests create their own data; seeded data would be implicit dependency
- `TESTING = True` — exceptions propagate to pytest instead of being swallowed by Flask's error handler
- Fixture scope is function (default) — fresh isolated DB per test, order-independent

---

### 7. `tests/test_login_logout.py` — 13 Tests

**Helper (module-level):**
```python
from werkzeug.security import generate_password_hash
import database.db as db_module

def _insert_user(email="test@example.com", password="password123"):
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", email, generate_password_hash(password)),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id
```

**Test groups and assertions:**

| # | Test | Setup | Assert |
|---|---|---|---|
| 1 | `test_login_get_returns_200` | `GET /login` | status 200 |
| 2 | `test_login_get_renders_form` | `GET /login` | `b"Welcome back"` in body |
| 3 | `test_login_blank_email` | POST `email=""` | 200, `b"Email is required."` |
| 4 | `test_login_blank_password` | POST `password=""` | 200, `b"Password is required."` |
| 5 | `test_login_unknown_email` | No user; POST unknown email | 200, `b"Invalid email or password."` |
| 6 | `test_login_wrong_password` | Insert user; POST wrong password | 200, `b"Invalid email or password."` |
| 7 | `test_login_success_redirects` | Insert user; POST correct creds | 302, `Location` ends with `/profile` |
| 8 | `test_login_success_sets_session` | Insert user; POST correct creds | `session["user_id"] == inserted_id` |
| 9 | `test_login_clears_old_session` | Set stale session; POST correct creds | `session["user_id"]` == new user id, not 9999 |
| 10 | `test_logout_redirects_to_landing` | `GET /logout` | 302, `Location` ends with `/` |
| 11 | `test_logout_clears_session` | Set session; `GET /logout` | `"user_id"` not in session |
| 12 | `test_logout_when_already_logged_out` | No session; `GET /logout` | 302 to `/`, no exception |
| 13 | `test_nav_shows_logout_when_logged_in` | Set session; `GET /` | `b"Logout"` in body |

**Session inspection pattern:**
```python
# Read session after request
with client.session_transaction() as sess:
    assert sess.get("user_id") == expected_id

# Set session before request
with client.session_transaction() as sess:
    sess["user_id"] = 42
```

---

## Pitfalls to Avoid

1. **Import order matters** — implement `get_user_by_email` in `db.py` before adding it to `app.py` import; server will crash on start otherwise
2. **`session.get()` in Jinja2** — always `.get()`, never direct key access; Jinja2 raises `UndefinedError` not `None` on missing keys
3. **`follow_redirects` in Flask 3.x** — default is `False`; be explicit in tests that check redirect status codes
4. **`_insert_user` runs after `app` fixture** — it calls `db_module.get_db()` which reads the patched `DB_PATH`; only call it inside test functions, never at module level

---

## Verification

```bash
# 1. Start server — no ImportError or AttributeError
python app.py

# 2. Manual smoke test
# Visit http://localhost:5001/login
# Submit demo@spendly.com / demo123 → redirects to /profile stub
# Nav should show "Logout" after login
# Click Logout → lands on /, nav shows "Sign in" + "Get started"
# Submit wrong password → "Invalid email or password."
# Submit blank email → "Email is required."

# 3. Run tests
pytest tests/test_login_logout.py -v
```
