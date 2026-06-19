# tests/test_07-add-expense.py
"""
Test suite for Step 07: Add Expense.

Spec: .claude/specs/07-add-expense.md
Routes:
    GET  /expenses/add  — render the add-expense form (logged-in only)
    POST /expenses/add  — validate and insert expense, redirect to /profile

Definition-of-done coverage
────────────────────────────
DoD 1.  GET /expenses/add while logged out → redirect /login
DoD 2.  POST /expenses/add while logged out → redirect /login
DoD 3.  GET /expenses/add while logged in → 200, form rendered
DoD 4.  Valid POST → row inserted in expenses, redirect to /profile
DoD 5.  New expense appears at top of expense list on /profile
DoD 6.  Blank amount → validation error, form re-rendered
DoD 7.  Amount = 0 → validation error
DoD 8.  Negative amount → validation error
DoD 9.  Non-numeric amount → validation error
DoD 10. Invalid date format → validation error
DoD 11. Category not in allowed list → validation error
DoD 12. Description optional — blank description submits successfully
DoD 13. "Add Expense" link on profile page navigates to /expenses/add
DoD 14. Form action uses url_for() — resolves to /expenses/add
DoD 15. On validation failure, previously entered values preserved in form

Additional edge-case groups
────────────────────────────
A.  All seven allowed categories accepted individually
B.  Empty category string rejected
C.  Blank date field rejected
D.  Whitespace-only amount rejected (treated as blank)
E.  Amount at minimum boundary (0.01) accepted
F.  Very large amount accepted (REAL storage)
G.  Stale session (user_id not in DB) redirects to /login on GET
H.  DB side effect: expenses row has correct user_id, amount, category, date,
    description, and description=None when blank
I.  Disallowed HTTP method on add-expense page (PUT) returns 405
"""

import pytest
from werkzeug.security import generate_password_hash
import database.db as db_module


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _insert_user(name="Riya Sharma", email="riya@example.com",
                 password="SecurePass1"):
    """Insert a test user directly into the DB; return the new user_id."""
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
    """Insert a single expense row for the given user."""
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    conn.close()


def _login(client, user_id):
    """Inject user_id directly into the session (bypasses login form)."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _post_expense(client, amount="500", category="Food",
                  date="2026-06-15", description="Test lunch"):
    """POST to /expenses/add with the given field values."""
    return client.post(
        "/expenses/add",
        data={
            "amount": amount,
            "category": category,
            "date": date,
            "description": description,
        },
    )


def _count_expenses(user_id):
    """Return total rows in expenses table for user_id."""
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def _fetch_last_expense(user_id):
    """Return the most-recently inserted expense row for user_id as a sqlite3.Row."""
    conn = db_module.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# DoD 1 & 2 — Auth guard: unauthenticated requests redirect to /login
# ---------------------------------------------------------------------------

class TestAuthGuard:
    """Both GET and POST must redirect unauthenticated users to /login."""

    def test_get_unauthenticated_redirects_to_login(self, client):
        """GET /expenses/add without a session must return 302 → /login."""
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert response.location.endswith("/login")

    def test_get_unauthenticated_does_not_render_form(self, client):
        """Unauthenticated GET must not return any form HTML."""
        response = client.get("/expenses/add")
        assert b"Add Expense" not in response.data
        assert b"amount" not in response.data

    def test_post_unauthenticated_redirects_to_login(self, client):
        """POST /expenses/add without a session must return 302 → /login."""
        response = _post_expense(client)
        assert response.status_code == 302
        assert response.location.endswith("/login")

    def test_post_unauthenticated_no_row_inserted(self, client):
        """An unauthenticated POST must not write anything to the expenses table."""
        _post_expense(client)
        conn = db_module.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM expenses")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_get_no_session_at_all_redirects_to_login(self, client):
        """A GET with an entirely empty session (no user_id key) must redirect to /login."""
        # Ensure the session really is empty before the request
        with client.session_transaction() as sess:
            sess.clear()
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert response.location.endswith("/login")

    def test_get_follow_redirect_lands_on_login_page(self, client):
        """Following the redirect of an unauthenticated GET must render the login page."""
        response = client.get("/expenses/add", follow_redirects=True)
        assert response.status_code == 200
        assert b"Login" in response.data or b"login" in response.data.lower()


# ---------------------------------------------------------------------------
# DoD 3 — GET /expenses/add while logged in renders the form
# ---------------------------------------------------------------------------

class TestGetAddExpenseForm:
    """Authenticated GET must render the add-expense form with all required elements."""

    def test_get_authenticated_returns_200(self, client):
        """GET /expenses/add for a logged-in user must return HTTP 200."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert response.status_code == 200

    def test_get_renders_add_expense_heading(self, client):
        """The page must contain the 'Add Expense' heading."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b"Add Expense" in response.data

    def test_get_renders_amount_field(self, client):
        """The form must include an input named 'amount'."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b'name="amount"' in response.data

    def test_get_renders_category_dropdown(self, client):
        """The form must include a select element named 'category'."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b'name="category"' in response.data

    def test_get_renders_date_field(self, client):
        """The form must include an input named 'date'."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b'name="date"' in response.data

    def test_get_renders_description_field(self, client):
        """The form must include an input named 'description'."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b'name="description"' in response.data

    def test_get_renders_all_seven_categories(self, client):
        """All seven allowed category options must appear in the dropdown."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        for category in [b"Food", b"Transport", b"Bills", b"Health",
                         b"Entertainment", b"Shopping", b"Other"]:
            assert category in response.data

    def test_get_form_action_points_to_add_expense_view(self, client):
        """The form action must resolve to /expenses/add (via url_for)."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b'action="/expenses/add"' in response.data

    def test_get_no_error_shown_on_initial_load(self, client):
        """No validation error should appear on the initial GET."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b"auth-error" not in response.data

    def test_get_back_link_points_to_profile(self, client):
        """A back-to-profile link must be present and point to /profile."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b'href="/profile"' in response.data


# ---------------------------------------------------------------------------
# DoD 4 — Valid POST inserts row and redirects to /profile
# ---------------------------------------------------------------------------

class TestValidPostSubmission:
    """A POST with all valid fields must insert exactly one row and redirect."""

    def test_valid_post_returns_302(self, client):
        """A valid POST must return a 302 redirect."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client)
        assert response.status_code == 302

    def test_valid_post_redirects_to_profile(self, client):
        """A valid POST must redirect to /profile."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client)
        assert response.location.endswith("/profile")

    def test_valid_post_inserts_one_row(self, client):
        """A valid POST must insert exactly one row in the expenses table."""
        user_id = _insert_user()
        _login(client, user_id)
        assert _count_expenses(user_id) == 0
        _post_expense(client, amount="750", category="Transport",
                      date="2026-06-10", description="Auto ride")
        assert _count_expenses(user_id) == 1

    def test_valid_post_stores_correct_user_id(self, client):
        """The inserted row must carry the session user_id."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="200", category="Food",
                      date="2026-06-12", description="Lunch")
        row = _fetch_last_expense(user_id)
        assert row["user_id"] == user_id

    def test_valid_post_stores_correct_amount(self, client):
        """The inserted row must store the submitted amount as a float."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="1234.56", category="Bills",
                      date="2026-06-05", description="Electricity")
        row = _fetch_last_expense(user_id)
        assert abs(row["amount"] - 1234.56) < 0.001

    def test_valid_post_stores_correct_category(self, client):
        """The inserted row must store the submitted category string."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="500", category="Health",
                      date="2026-06-08", description="Pharmacy")
        row = _fetch_last_expense(user_id)
        assert row["category"] == "Health"

    def test_valid_post_stores_correct_date(self, client):
        """The inserted row must store the date in YYYY-MM-DD format."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="300", category="Shopping",
                      date="2026-06-20", description="Kurta")
        row = _fetch_last_expense(user_id)
        assert row["date"] == "2026-06-20"

    def test_valid_post_stores_correct_description(self, client):
        """The inserted row must store the submitted description text."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="150", category="Other",
                      date="2026-06-18", description="Notebook purchase")
        row = _fetch_last_expense(user_id)
        assert row["description"] == "Notebook purchase"

    def test_valid_post_follow_redirect_renders_profile(self, client):
        """Following the redirect after a valid POST must render the profile page."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "400", "category": "Food",
                  "date": "2026-06-15", "description": "Dinner"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Recent Transactions" in response.data


# ---------------------------------------------------------------------------
# DoD 5 — New expense appears at top of expense list on /profile
# ---------------------------------------------------------------------------

class TestNewExpenseOnProfile:
    """After a successful add, the new expense must be visible on /profile."""

    def test_new_expense_description_visible_on_profile(self, client):
        """The description of the newly added expense must appear on the profile page."""
        user_id = _insert_user()
        _login(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "999", "category": "Entertainment",
                  "date": "2026-06-19", "description": "OTT renewal"},
        )
        response = client.get("/profile")
        assert b"OTT renewal" in response.data

    def test_new_expense_category_visible_on_profile(self, client):
        """The category of the newly added expense must appear on the profile page."""
        user_id = _insert_user()
        _login(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "600", "category": "Shopping",
                  "date": "2026-06-19", "description": "Shoes"},
        )
        response = client.get("/profile")
        assert b"Shopping" in response.data

    def test_new_expense_amount_visible_on_profile(self, client):
        """The formatted amount of the newly added expense must appear on the profile page."""
        user_id = _insert_user()
        _login(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "3500", "category": "Bills",
                  "date": "2026-06-19", "description": "Rent"},
        )
        response = client.get("/profile")
        assert "₹3,500".encode() in response.data

    def test_new_expense_appears_above_older_expense(self, client):
        """A newer expense must appear before an older one in the transactions table."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-01", "Old breakfast")
        _login(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "200", "category": "Health",
                  "date": "2026-06-19", "description": "New vitamins"},
        )
        response = client.get("/profile")
        html = response.data.decode()
        new_pos = html.find("New vitamins")
        old_pos = html.find("Old breakfast")
        assert new_pos < old_pos


# ---------------------------------------------------------------------------
# DoD 6 — Blank amount shows validation error
# ---------------------------------------------------------------------------

class TestBlankAmount:
    """Submitting with a blank amount field must re-render the form with an error."""

    def test_blank_amount_returns_200(self, client):
        """A POST with no amount must return HTTP 200 (form re-rendered, not redirect)."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="")
        assert response.status_code == 200

    def test_blank_amount_shows_required_error(self, client):
        """Blank amount must display the 'Amount is required.' error message."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="")
        assert b"Amount is required." in response.data

    def test_blank_amount_no_row_inserted(self, client):
        """A POST with blank amount must not insert any row in the expenses table."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="")
        assert _count_expenses(user_id) == 0

    def test_whitespace_only_amount_shows_required_error(self, client):
        """An amount containing only spaces must be treated as blank and show an error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="   ")
        assert response.status_code == 200
        assert b"Amount is required." in response.data

    def test_whitespace_only_amount_no_row_inserted(self, client):
        """Whitespace-only amount must not insert any row in the expenses table."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="   ")
        assert _count_expenses(user_id) == 0


# ---------------------------------------------------------------------------
# DoD 7 & 8 — Zero and negative amounts rejected
# ---------------------------------------------------------------------------

class TestZeroAndNegativeAmount:
    """Zero and negative amounts must be rejected with a validation error."""

    def test_zero_amount_returns_200(self, client):
        """Amount = 0 must return HTTP 200 (not a redirect)."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="0")
        assert response.status_code == 200

    def test_zero_amount_shows_error(self, client):
        """Amount = 0 must display the 'greater than zero' error message."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="0")
        assert b"Amount must be greater than zero." in response.data

    def test_zero_amount_no_row_inserted(self, client):
        """Amount = 0 must not insert any row in the expenses table."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="0")
        assert _count_expenses(user_id) == 0

    def test_negative_amount_returns_200(self, client):
        """A negative amount must return HTTP 200 (not a redirect)."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="-100")
        assert response.status_code == 200

    def test_negative_amount_shows_error(self, client):
        """A negative amount must display the 'greater than zero' error message."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="-100")
        assert b"Amount must be greater than zero." in response.data

    def test_negative_amount_no_row_inserted(self, client):
        """A negative amount must not insert any row in the expenses table."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="-100")
        assert _count_expenses(user_id) == 0

    def test_negative_float_amount_shows_error(self, client):
        """A negative decimal amount (-0.01) must also be rejected."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="-0.01")
        assert b"Amount must be greater than zero." in response.data

    def test_zero_float_amount_shows_error(self, client):
        """Amount 0.00 must be rejected the same as integer zero."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="0.00")
        assert b"Amount must be greater than zero." in response.data


# ---------------------------------------------------------------------------
# DoD 9 — Non-numeric amount rejected
# ---------------------------------------------------------------------------

class TestNonNumericAmount:
    """A non-numeric string in the amount field must trigger a validation error."""

    def test_alpha_amount_returns_200(self, client):
        """Alphabetic text as amount must return HTTP 200."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="abc")
        assert response.status_code == 200

    def test_alpha_amount_shows_number_error(self, client):
        """Alphabetic text as amount must display the 'must be a number' error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="abc")
        assert b"Amount must be a number." in response.data

    def test_alpha_amount_no_row_inserted(self, client):
        """Non-numeric amount must not insert any row."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="abc")
        assert _count_expenses(user_id) == 0

    def test_currency_symbol_amount_shows_number_error(self, client):
        """An amount prefixed with the rupee symbol must be rejected as non-numeric."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="₹500")
        assert b"Amount must be a number." in response.data

    def test_comma_formatted_amount_shows_number_error(self, client):
        """A comma-formatted amount (e.g. '1,000') must be rejected as non-numeric."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="1,000")
        assert b"Amount must be a number." in response.data


# ---------------------------------------------------------------------------
# DoD 10 — Invalid date format shows validation error
# ---------------------------------------------------------------------------

class TestInvalidDateFormat:
    """Dates not matching YYYY-MM-DD must be rejected."""

    def test_blank_date_shows_required_error(self, client):
        """An empty date field must display the 'Date is required.' error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="")
        assert response.status_code == 200
        assert b"Date is required." in response.data

    def test_blank_date_no_row_inserted(self, client):
        """A missing date must not insert any row."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, date="")
        assert _count_expenses(user_id) == 0

    def test_slash_separated_date_shows_format_error(self, client):
        """A DD/MM/YYYY date must fail the _DATE_RE check and show a format error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="15/06/2026")
        assert response.status_code == 200
        assert b"Invalid date. Use YYYY-MM-DD format." in response.data

    def test_slash_separated_date_no_row_inserted(self, client):
        """A slash-formatted date must not insert any row."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, date="15/06/2026")
        assert _count_expenses(user_id) == 0

    def test_dotted_date_shows_format_error(self, client):
        """A DD.MM.YYYY date must be rejected with a format error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="15.06.2026")
        assert b"Invalid date. Use YYYY-MM-DD format." in response.data

    def test_plain_text_date_shows_format_error(self, client):
        """A plain text string as the date must be rejected with a format error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="not-a-date")
        assert b"Invalid date. Use YYYY-MM-DD format." in response.data

    def test_partial_date_shows_format_error(self, client):
        """A partial date string (YYYY-MM only) must be rejected."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="2026-06")
        assert b"Invalid date. Use YYYY-MM-DD format." in response.data

    def test_invalid_month_shows_format_error(self, client):
        """A date with month 13 must fail the regex and show a format error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="2026-13-01")
        assert b"Invalid date. Use YYYY-MM-DD format." in response.data

    def test_invalid_day_shows_format_error(self, client):
        """A date with day 32 must fail the regex and show a format error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="2026-06-32")
        assert b"Invalid date. Use YYYY-MM-DD format." in response.data

    def test_valid_yyyy_mm_dd_accepted(self, client):
        """A correctly formatted YYYY-MM-DD date must pass validation."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, date="2026-06-15")
        assert response.status_code == 302
        assert response.location.endswith("/profile")


# ---------------------------------------------------------------------------
# DoD 11 — Invalid category rejected
# ---------------------------------------------------------------------------

class TestInvalidCategory:
    """Category values not in the allowed list must be rejected."""

    def test_empty_category_shows_error(self, client):
        """An empty string category (placeholder option) must be rejected."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, category="")
        assert response.status_code == 200
        assert b"Please select a valid category." in response.data

    def test_empty_category_no_row_inserted(self, client):
        """An empty category must not insert any row."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, category="")
        assert _count_expenses(user_id) == 0

    def test_freetext_category_shows_error(self, client):
        """A category value not in the allowed list must be rejected."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, category="Groceries")
        assert response.status_code == 200
        assert b"Please select a valid category." in response.data

    def test_freetext_category_no_row_inserted(self, client):
        """An invalid category must not insert any row."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, category="Groceries")
        assert _count_expenses(user_id) == 0

    def test_lowercase_category_shows_error(self, client):
        """Category matching is case-sensitive; 'food' must be rejected."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, category="food")
        assert b"Please select a valid category." in response.data

    def test_sql_injection_category_shows_error(self, client):
        """A SQL-injection string as category must be rejected (not in allowed list)."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, category="Food'; DROP TABLE expenses;--")
        assert b"Please select a valid category." in response.data

    def test_sql_injection_category_no_row_inserted(self, client):
        """A SQL-injection category must not insert any row or corrupt the DB."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, category="Food'; DROP TABLE expenses;--")
        # If the table were dropped this would raise; it must return 0
        assert _count_expenses(user_id) == 0


# ---------------------------------------------------------------------------
# DoD 12 — Description is optional
# ---------------------------------------------------------------------------

class TestOptionalDescription:
    """Leaving description blank must not prevent a successful submission."""

    def test_blank_description_submits_successfully(self, client):
        """A POST with a blank description must redirect to /profile."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, description="")
        assert response.status_code == 302
        assert response.location.endswith("/profile")

    def test_blank_description_inserts_row(self, client):
        """A POST with blank description must insert exactly one row."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, description="")
        assert _count_expenses(user_id) == 1

    def test_blank_description_stored_as_none_in_db(self, client):
        """A blank description must be stored as NULL (None) in the DB."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, description="")
        row = _fetch_last_expense(user_id)
        assert row["description"] is None

    def test_whitespace_description_stored_as_none(self, client):
        """A whitespace-only description must also be stored as NULL after strip."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, description="   ")
        row = _fetch_last_expense(user_id)
        # Route strips whitespace; add_expense stores None when empty
        assert row["description"] is None

    def test_provided_description_stored_as_text(self, client):
        """A non-empty description must be stored as plain text (not None)."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, description="Pharmacy vitamins")
        row = _fetch_last_expense(user_id)
        assert row["description"] == "Pharmacy vitamins"


# ---------------------------------------------------------------------------
# DoD 13 — "Add Expense" link on profile page navigates to /expenses/add
# ---------------------------------------------------------------------------

class TestProfilePageAddExpenseLink:
    """The profile page must contain a link pointing to /expenses/add."""

    def test_profile_has_add_expense_link(self, client):
        """The profile page must include an anchor tag with href=/expenses/add."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/profile")
        assert b'href="/expenses/add"' in response.data

    def test_profile_add_expense_link_has_visible_text(self, client):
        """The Add Expense link must have visible text on the profile page."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/profile")
        assert b"Add Expense" in response.data


# ---------------------------------------------------------------------------
# DoD 14 — Form action uses url_for (resolves to /expenses/add)
# ---------------------------------------------------------------------------

class TestFormActionUsesUrlFor:
    """The form action attribute must resolve to the correct route URL."""

    def test_form_action_resolves_to_expenses_add(self, client):
        """The <form> action on add_expense.html must equal /expenses/add."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/expenses/add")
        assert b'action="/expenses/add"' in response.data


# ---------------------------------------------------------------------------
# DoD 15 — Validation failure preserves previously entered values in form
# ---------------------------------------------------------------------------

class TestFormValuePreservationOnError:
    """When validation fails, all previously entered field values must be echoed back."""

    def test_category_preserved_on_amount_error(self, client):
        """The selected category must be preserved in the form when amount is blank."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "", "category": "Transport",
                  "date": "2026-06-15", "description": "Bus pass"},
        )
        assert b"Transport" in response.data

    def test_date_preserved_on_amount_error(self, client):
        """The entered date must be preserved in the form when amount is invalid."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "", "category": "Food",
                  "date": "2026-06-20", "description": "Dinner"},
        )
        assert b"2026-06-20" in response.data

    def test_description_preserved_on_amount_error(self, client):
        """The entered description must be preserved in the form when amount is blank."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "", "category": "Food",
                  "date": "2026-06-15", "description": "Biryani takeaway"},
        )
        assert b"Biryani takeaway" in response.data

    def test_amount_preserved_on_invalid_date_error(self, client):
        """The entered amount must be preserved when the date fails validation."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "999", "category": "Health",
                  "date": "bad-date", "description": "Checkup"},
        )
        assert b"999" in response.data

    def test_category_preserved_on_invalid_date_error(self, client):
        """The selected category must be preserved when the date fails validation."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "500", "category": "Entertainment",
                  "date": "bad-date", "description": "Movie"},
        )
        assert b"Entertainment" in response.data

    def test_description_preserved_on_invalid_category(self, client):
        """The entered description must be preserved when category is invalid."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "300", "category": "InvalidCat",
                  "date": "2026-06-15", "description": "Coffee beans"},
        )
        assert b"Coffee beans" in response.data

    def test_amount_preserved_on_invalid_category(self, client):
        """The entered amount must be preserved when category is invalid."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.post(
            "/expenses/add",
            data={"amount": "450", "category": "InvalidCat",
                  "date": "2026-06-15", "description": "Snacks"},
        )
        assert b"450" in response.data


# ---------------------------------------------------------------------------
# Edge case A — All seven allowed categories accepted
# ---------------------------------------------------------------------------

class TestAllowedCategoriesAccepted:
    """Each of the seven categories must be accepted individually."""

    @pytest.mark.parametrize("category", [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ])
    def test_valid_category_redirects_to_profile(self, client, category):
        """A POST with each allowed category must redirect to /profile."""
        user_id = _insert_user(
            email=f"user_{category.lower()}@example.com"
        )
        _login(client, user_id)
        response = _post_expense(client, category=category)
        assert response.status_code == 302
        assert response.location.endswith("/profile")

    @pytest.mark.parametrize("category", [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ])
    def test_valid_category_inserts_row(self, client, category):
        """A POST with each allowed category must insert one row in the DB."""
        user_id = _insert_user(
            email=f"row_{category.lower()}@example.com"
        )
        _login(client, user_id)
        _post_expense(client, category=category)
        assert _count_expenses(user_id) == 1


# ---------------------------------------------------------------------------
# Edge case E — Minimum boundary amount (0.01) accepted
# ---------------------------------------------------------------------------

class TestMinimumBoundaryAmount:
    """The smallest meaningful positive amount must be accepted."""

    def test_amount_0_01_redirects_to_profile(self, client):
        """Amount = 0.01 (one paisa) must pass validation and redirect."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="0.01")
        assert response.status_code == 302
        assert response.location.endswith("/profile")

    def test_amount_0_01_stored_correctly(self, client):
        """Amount = 0.01 must be stored as 0.01 in the DB."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="0.01")
        row = _fetch_last_expense(user_id)
        assert abs(row["amount"] - 0.01) < 0.0001


# ---------------------------------------------------------------------------
# Edge case F — Very large amount accepted
# ---------------------------------------------------------------------------

class TestLargeAmount:
    """REAL storage in SQLite must handle large rupee values without error."""

    def test_large_amount_redirects_to_profile(self, client):
        """A very large amount (e.g. ₹10,00,000) must be accepted."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="1000000")
        assert response.status_code == 302
        assert response.location.endswith("/profile")

    def test_large_amount_stored_correctly(self, client):
        """A large amount must be stored as-is (no truncation)."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="1000000")
        row = _fetch_last_expense(user_id)
        assert abs(row["amount"] - 1_000_000) < 0.001


# ---------------------------------------------------------------------------
# Edge case H — DB side effects verified thoroughly
# ---------------------------------------------------------------------------

class TestDbSideEffects:
    """Row-level DB verification for the full set of stored fields."""

    def test_multiple_expenses_each_get_separate_row(self, client):
        """Posting two expenses must create two distinct rows, not one."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="100", category="Food",
                      date="2026-06-10", description="First")
        _post_expense(client, amount="200", category="Bills",
                      date="2026-06-11", description="Second")
        assert _count_expenses(user_id) == 2

    def test_expenses_of_different_users_are_isolated(self, client):
        """An expense inserted for user A must not appear in user B's expenses."""
        user_a = _insert_user(name="User A", email="user_a@example.com")
        user_b = _insert_user(name="User B", email="user_b@example.com")
        _login(client, user_a)
        _post_expense(client, amount="500", category="Food",
                      date="2026-06-15", description="User A meal")
        assert _count_expenses(user_b) == 0

    def test_full_row_fields_correct_after_valid_post(self, client):
        """Every column in the inserted row must match the submitted values exactly."""
        user_id = _insert_user()
        _login(client, user_id)
        _post_expense(client, amount="1999.50", category="Shopping",
                      date="2026-06-17", description="Handbag")
        row = _fetch_last_expense(user_id)
        assert row["user_id"] == user_id
        assert abs(row["amount"] - 1999.50) < 0.001
        assert row["category"] == "Shopping"
        assert row["date"] == "2026-06-17"
        assert row["description"] == "Handbag"

    def test_sql_injection_in_description_stored_safely(self, client):
        """A SQL-injection string in description must be stored as literal text."""
        user_id = _insert_user()
        _login(client, user_id)
        malicious = "nice'); DROP TABLE expenses;--"
        _post_expense(client, description=malicious)
        # Table must still exist and have one row
        assert _count_expenses(user_id) == 1
        row = _fetch_last_expense(user_id)
        assert row["description"] == malicious

    def test_sql_injection_in_amount_rejected_as_non_numeric(self, client):
        """A SQL-injection string in the amount field must be rejected as non-numeric."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _post_expense(client, amount="1; DROP TABLE expenses;--")
        assert b"Amount must be a number." in response.data
        assert _count_expenses(user_id) == 0


# ---------------------------------------------------------------------------
# Edge case I — Disallowed HTTP method returns 405
# ---------------------------------------------------------------------------

class TestDisallowedHttpMethod:
    """HTTP methods other than GET and POST must not be accepted by the route."""

    def test_put_to_add_expense_returns_405(self, client):
        """PUT /expenses/add must return HTTP 405 Method Not Allowed."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.put(
            "/expenses/add",
            data={"amount": "500", "category": "Food",
                  "date": "2026-06-15", "description": "Test"},
        )
        assert response.status_code == 405

    def test_delete_to_add_expense_returns_405(self, client):
        """DELETE /expenses/add must return HTTP 405 Method Not Allowed."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.delete("/expenses/add")
        assert response.status_code == 405
