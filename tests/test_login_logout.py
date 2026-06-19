import pytest
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


# --- GET /login ---

def test_login_get_returns_200(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_login_get_renders_form(client):
    response = client.get("/login")
    assert b"Welcome back" in response.data


# --- POST /login — blank fields ---

def test_login_blank_email(client):
    response = client.post("/login", data={"email": "", "password": "anything"})
    assert response.status_code == 200
    assert b"Email is required." in response.data


def test_login_blank_password(client):
    response = client.post("/login", data={"email": "a@b.com", "password": ""})
    assert response.status_code == 200
    assert b"Password is required." in response.data


# --- POST /login — credential failures ---

def test_login_unknown_email(client):
    response = client.post("/login", data={"email": "no@one.com", "password": "password123"})
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_login_wrong_password(client):
    _insert_user()
    response = client.post("/login", data={"email": "test@example.com", "password": "wrongpass"})
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


# --- POST /login — success ---

def test_login_success_redirects(client):
    _insert_user()
    response = client.post("/login", data={"email": "test@example.com", "password": "password123"})
    assert response.status_code == 302
    assert response.location.endswith("/profile")


def test_login_success_sets_session(client):
    user_id = _insert_user()
    client.post("/login", data={"email": "test@example.com", "password": "password123"})
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user_id


def test_login_clears_old_session(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    client.post("/login", data={"email": "test@example.com", "password": "password123"})
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user_id


# --- GET /logout ---

def test_logout_redirects_to_landing(client):
    response = client.post("/logout")
    assert response.status_code == 302
    assert response.location.endswith("/")


def test_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 42
    client.post("/logout")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_when_already_logged_out(client):
    response = client.post("/logout")
    assert response.status_code == 302
    assert response.location.endswith("/")


# --- base.html nav ---

def test_nav_shows_login_when_anonymous(client):
    response = client.get("/")
    assert b"Sign in" in response.data
    assert b"Get started" in response.data


def test_nav_shows_logout_when_logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    response = client.get("/")
    assert b"Logout" in response.data
    assert b"Sign in" not in response.data
