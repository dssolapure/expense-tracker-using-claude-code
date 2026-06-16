import pytest
from werkzeug.security import check_password_hash, generate_password_hash
from database.db import create_user, get_db


# ---------------------------------------------------------------------------
# GET /register
# ---------------------------------------------------------------------------

def test_register_get_returns_200(client):
    response = client.get("/register")
    assert response.status_code == 200


def test_register_get_renders_form(client):
    response = client.get("/register")
    assert b"Create your account" in response.data


# ---------------------------------------------------------------------------
# POST /register — happy path
# ---------------------------------------------------------------------------

def test_register_post_valid_redirects(client):
    response = client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "secure123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_register_post_creates_user_in_db(client, app):
    client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "secure123"},
    )
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", ("alice@example.com",)
        ).fetchone()
        conn.close()
    assert row is not None
    assert row["name"] == "Alice"


def test_register_password_is_hashed(client, app):
    client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "secure123"},
    )
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", ("alice@example.com",)
        ).fetchone()
        conn.close()
    assert row["password_hash"] != "secure123"
    assert check_password_hash(row["password_hash"], "secure123")


# ---------------------------------------------------------------------------
# POST /register — validation failures
# ---------------------------------------------------------------------------

def test_register_blank_name(client):
    response = client.post(
        "/register",
        data={"name": "", "email": "bob@example.com", "password": "secure123"},
    )
    assert response.status_code == 200
    assert b"Name is required" in response.data


def test_register_blank_email(client):
    response = client.post(
        "/register",
        data={"name": "Bob", "email": "", "password": "secure123"},
    )
    assert response.status_code == 200
    assert b"Email is required" in response.data


def test_register_blank_password(client):
    response = client.post(
        "/register",
        data={"name": "Bob", "email": "bob@example.com", "password": ""},
    )
    assert response.status_code == 200
    assert b"Password is required" in response.data


def test_register_short_password(client):
    response = client.post(
        "/register",
        data={"name": "Bob", "email": "bob@example.com", "password": "abc"},
    )
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data


def test_register_password_7_chars_fails(client):
    response = client.post(
        "/register",
        data={"name": "Bob", "email": "bob@example.com", "password": "1234567"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data


def test_register_password_8_chars_succeeds(client):
    response = client.post(
        "/register",
        data={"name": "Bob", "email": "bob@example.com", "password": "12345678"},
        follow_redirects=False,
    )
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# POST /register — duplicate email
# ---------------------------------------------------------------------------

def test_register_duplicate_email(client):
    client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "secure123"},
    )
    response = client.post(
        "/register",
        data={"name": "Alice2", "email": "alice@example.com", "password": "different1"},
    )
    assert response.status_code == 200
    assert b"An account with that email already exists." in response.data


def test_register_duplicate_no_second_row(client, app):
    client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "secure123"},
    )
    client.post(
        "/register",
        data={"name": "Alice2", "email": "alice@example.com", "password": "different1"},
    )
    with app.app_context():
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", ("alice@example.com",)
        ).fetchone()[0]
        conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# create_user() unit tests — DB layer directly
# ---------------------------------------------------------------------------

def test_create_user_returns_id(app):
    with app.app_context():
        user_id = create_user("Carol", "carol@example.com", generate_password_hash("pass1234"))
    assert isinstance(user_id, int)
    assert user_id > 0


def test_create_user_duplicate_returns_none(app):
    with app.app_context():
        first = create_user("Carol", "carol@example.com", generate_password_hash("pass1234"))
        second = create_user("Carol2", "carol@example.com", generate_password_hash("pass5678"))
    assert isinstance(first, int)
    assert second is None
