import pytest
from werkzeug.security import generate_password_hash
import database.db as db_module


def _insert_user(email="profile@example.com", password="password123"):
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Dayanand Solapure", email, generate_password_hash(password)),
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


# --- Unauthenticated access ---

def test_profile_without_session_redirects(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.location.endswith("/login")


def test_profile_without_session_does_not_render_page(client):
    response = client.get("/profile", follow_redirects=False)
    assert b"Dayanand Solapure" not in response.data


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
    assert b"Dayanand Solapure" in response.data


def test_profile_shows_user_email(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"profile@example.com" in response.data


def test_profile_shows_total_spent(client):
    user_id = _insert_user()
    _insert_expense(user_id, 2500.00, "Bills", "2026-06-15", "Electricity bill")
    _insert_expense(user_id, 1000.00, "Food",  "2026-06-10", "Groceries")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert "₹3,500".encode() in response.data


def test_profile_shows_transaction_count(client):
    user_id = _insert_user()
    _insert_expense(user_id, 100.00, "Food",      "2026-06-01", "Breakfast")
    _insert_expense(user_id, 200.00, "Transport", "2026-06-02", "Bus")
    _insert_expense(user_id, 300.00, "Health",    "2026-06-03", "Medicine")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"3" in response.data


def test_profile_shows_top_category(client):
    user_id = _insert_user()
    _insert_expense(user_id, 5000.00, "Health", "2026-06-01", "Hospital")
    _insert_expense(user_id,  500.00, "Food",   "2026-06-02", "Lunch")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Health" in response.data


def test_profile_stats_zero_expenses(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert "₹0".encode() in response.data
    assert "—".encode("utf-8") in response.data


def test_profile_shows_transaction_table(client):
    user_id = _insert_user()
    _insert_expense(user_id, 2500.00, "Bills",         "2026-06-15", "Electricity bill")
    _insert_expense(user_id,  499.00, "Entertainment", "2026-06-11", "OTT subscription")
    _insert_expense(user_id,  850.00, "Transport",     "2026-06-03", "Monthly bus pass")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Electricity bill" in response.data
    assert b"OTT subscription" in response.data
    assert b"Monthly bus pass" in response.data


def test_profile_transaction_date_formatting(client):
    user_id = _insert_user()
    _insert_expense(user_id, 100.00, "Food", "2026-06-15", "Lunch")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"15 Jun 2026" in response.data


def test_profile_empty_expenses_renders_without_error(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert response.status_code == 200


def test_profile_shows_category_breakdown(client):
    user_id = _insert_user()
    _insert_expense(user_id, 2500.00, "Shopping",  "2026-06-01", "Clothes")
    _insert_expense(user_id,  850.00, "Transport", "2026-06-02", "Bus pass")
    _insert_expense(user_id,  600.00, "Health",    "2026-06-03", "Pharmacy")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Shopping" in response.data
    assert b"Transport" in response.data
    assert b"Health" in response.data


def test_profile_category_percentage_calculation(client):
    user_id = _insert_user()
    _insert_expense(user_id, 1000.00, "Bills", "2026-06-01", "Rent")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"100" in response.data


def test_profile_category_top_7_limit(client):
    user_id = _insert_user()
    data = [
        (700.00, "Bills"),
        (600.00, "Food"),
        (500.00, "Transport"),
        (400.00, "Health"),
        (300.00, "Shopping"),
        (200.00, "Entertainment"),
        (100.00, "Other"),
        ( 50.00, "Education"),
    ]
    for i, (amt, cat) in enumerate(data):
        _insert_expense(user_id, amt, cat, f"2026-06-{i+1:02d}", f"desc {i}")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Bills" in response.data
    assert b'cat-breakdown__name">Education' not in response.data


def test_profile_empty_categories_renders_without_error(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert response.status_code == 200


def test_profile_nav_shows_logout_when_logged_in(client):
    user_id = _insert_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    response = client.get("/profile")
    assert b"Logout" in response.data
    assert b"Sign in" not in response.data


def test_profile_stale_session_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.location.endswith("/login")


def test_profile_stale_session_clears_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    client.get("/profile")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
