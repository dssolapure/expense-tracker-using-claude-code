---
name: Spendly Test Fixture Patterns
description: Confirmed fixture, helper, and session manipulation patterns that work in this project's pytest setup
type: project
---

## conftest.py Pattern (tests/conftest.py)

The project uses a tempfile-backed SQLite DB (NOT :memory:) to avoid in-process sharing issues:

```python
import os, tempfile, pytest
import app as flask_app
import database.db as db_module
from database.db import init_db

@pytest.fixture()
def app():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_path          # redirect ALL db calls
    flask_app.app.config["TESTING"] = True
    with flask_app.app.app_context():
        db_module.init_db()
        init_db()
    yield flask_app.app
    db_module.DB_PATH = original_path
    os.unlink(db_path)

@pytest.fixture()
def client(app):
    return app.test_client()
```

Key: patch `db_module.DB_PATH` to isolate each test's DB. `seed_db()` is NOT called in tests — each test inserts its own data.

## Helper Functions Used in Tests

```python
from werkzeug.security import generate_password_hash
import database.db as db_module

def _insert_user(name, email, password):
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id

def _insert_expense(user_id, amount, category, date, description):
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    conn.close()
```

## Session Manipulation

```python
# Log in without going through the login form:
with client.session_transaction() as sess:
    sess["user_id"] = user_id

# Check session state:
with client.session_transaction() as sess:
    assert sess.get("user_id") == expected_id
    assert "user_id" not in sess   # after logout/clear
```

## Redirect Assertions

```python
assert response.status_code == 302
assert response.location.endswith("/login")    # or "/profile", "/"
# Follow redirect:
response = client.get("/profile", follow_redirects=True)
```

## Encoding Gotchas

- Rupee symbol and em-dash are multi-byte UTF-8; use `"₹3,500".encode()` or `"—".encode("utf-8")`
- For plain ASCII assertions: `assert b"Some text" in response.data`

**Why:** Confirmed working patterns from conftest.py and existing passing test files; saves future sessions from re-deriving fixture boilerplate.
**How to apply:** Copy these patterns directly into new test files without modification; always use `_insert_user` / `_insert_expense` helpers rather than calling route endpoints for setup.
