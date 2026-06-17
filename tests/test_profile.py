import pytest
from werkzeug.security import generate_password_hash
import database.db as db_module


def _insert_user(email="profile@example.com", password="password123"):
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Nitish Kumar", email, generate_password_hash(password)),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


# --- Unauthenticated access ---

def test_profile_without_session_redirects(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.location.endswith("/login")


def test_profile_without_session_does_not_render_page(client):
    response = client.get("/profile", follow_redirects=False)
    assert b"Nitish Kumar" not in response.data


# --- Authenticated access ---

def test_profile_with_session_returns_200(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert response.status_code == 200


def test_profile_shows_user_name(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Nitish Kumar" in response.data


def test_profile_shows_user_email(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"nitish@example.com" in response.data


def test_profile_shows_total_spent(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert "₹6,374".encode() in response.data


def test_profile_shows_transaction_count(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"8" in response.data


def test_profile_shows_top_category(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Bills" in response.data


def test_profile_shows_transaction_table(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Electricity bill" in response.data
    assert b"OTT subscription" in response.data
    assert b"Monthly bus pass" in response.data


def test_profile_shows_category_breakdown(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Shopping" in response.data
    assert b"Transport" in response.data
    assert b"Health" in response.data


def test_profile_nav_shows_logout_when_logged_in(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Logout" in response.data
    assert b"Sign in" not in response.data


def test_profile_stale_session_still_renders(client):
    """Step 4 guard checks only that user_id key exists in session,
    not that it maps to a real DB row — that validation is deferred to Step 5."""
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 200
