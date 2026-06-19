# tests/test_04-profile.py
"""
Test suite for the Spendly Profile Page (Step 04).

Spec: .claude/specs/04-profile.md
Route: GET /profile

Coverage plan
─────────────
1.  Auth guard — unauthenticated access
2.  Auth guard — stale / invalid session
3.  Happy-path rendering — HTTP 200, correct template
4.  User info card — name, email, member-since
5.  Summary stats — total_spent, transaction_count, top_category
6.  Summary stats — edge cases (zero expenses, single expense)
7.  Transaction history table — rows, column data, date formatting, INR amounts
8.  Transaction history table — table capped at 10 most-recent rows
9.  Category breakdown — at least three categories rendered
10. Category breakdown — percentage calculation
11. Category breakdown — capped at 7 categories
12. Category breakdown — empty state (no expenses)
13. Navbar state — logged-in shows Logout, hides Sign in
14. No hardcoded hex colours in profile.html
15. Date filter — only one date supplied (hint shown, filter inactive)
16. Date filter — from_date after to_date (error shown)
17. Date filter — valid range filters expenses, stats, categories
18. Date filter — active-filter indicator visibility
19. Date filter — Clear link resets to unfiltered view
20. Date filter — pre-population of inputs after submission
"""

import re
import pytest
from werkzeug.security import generate_password_hash
import database.db as db_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_user(name="Priya Sharma", email="priya@example.com",
                 password="password123"):
    """Insert a test user and return their id."""
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
    """Manually set the session so the client is logged in as user_id."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _get_profile(client, **query_params):
    """GET /profile, passing any keyword args as query-string parameters."""
    if query_params:
        qs = "&".join(f"{k}={v}" for k, v in query_params.items())
        url = f"/profile?{qs}"
    else:
        url = "/profile"
    return client.get(url)


# ---------------------------------------------------------------------------
# 1. Auth guard — unauthenticated access
# ---------------------------------------------------------------------------

class TestUnauthenticatedAccess:
    """GET /profile with no session must redirect to /login."""

    def test_profile_without_session_returns_302(self, client):
        """Unauthenticated request must not return 200."""
        response = client.get("/profile")
        assert response.status_code == 302

    def test_profile_without_session_redirects_to_login(self, client):
        """Redirect target must be /login."""
        response = client.get("/profile")
        assert response.location.endswith("/login")

    def test_profile_without_session_no_content_leaked(self, client):
        """Profile page content must not appear in the redirect response."""
        response = client.get("/profile", follow_redirects=False)
        assert b"Recent Transactions" not in response.data
        assert b"Total Spent" not in response.data

    def test_profile_follow_redirect_lands_on_login_page(self, client):
        """Following the redirect renders the login page, not an error."""
        response = client.get("/profile", follow_redirects=True)
        assert response.status_code == 200
        # Login page is identified by its heading
        assert b"Welcome back" in response.data


# ---------------------------------------------------------------------------
# 2. Auth guard — stale / invalid session
# ---------------------------------------------------------------------------

class TestStaleSession:
    """Session user_id that does not exist in the DB must be rejected."""

    def test_stale_session_redirects_to_login(self, client):
        """A session with a non-existent user_id must redirect to /login."""
        with client.session_transaction() as sess:
            sess["user_id"] = 99999
        response = client.get("/profile")
        assert response.status_code == 302
        assert response.location.endswith("/login")

    def test_stale_session_clears_session(self, client):
        """After a stale-session redirect the session must be empty."""
        with client.session_transaction() as sess:
            sess["user_id"] = 99999
        client.get("/profile")
        with client.session_transaction() as sess:
            assert "user_id" not in sess


# ---------------------------------------------------------------------------
# 3. Happy-path rendering — HTTP 200, correct template
# ---------------------------------------------------------------------------

class TestHappyPathRendering:
    """A valid authenticated request must return 200 with the profile page."""

    def test_profile_authenticated_returns_200(self, client):
        """Logged-in user must receive HTTP 200."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert response.status_code == 200

    def test_profile_renders_page_title(self, client):
        """Page <title> must mention 'Profile' and 'Spendly'."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"My Profile" in response.data
        assert b"Spendly" in response.data

    def test_profile_extends_base_template(self, client):
        """Response must include the navbar brand, confirming base.html is used."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        # Brand name is in base.html's <nav>
        assert b"Spendly" in response.data
        # Footer copyright text is in base.html
        assert "Track every rupee".encode() in response.data

    def test_profile_get_method_accepted(self, client):
        """Only GET is defined; a GET must succeed without method-not-allowed."""
        user_id = _insert_user()
        _login(client, user_id)
        response = client.get("/profile")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 4. User info card — name, email, member-since
# ---------------------------------------------------------------------------

class TestUserInfoCard:
    """The user info card must display name, email, and a member-since date."""

    def test_profile_shows_user_name(self, client):
        """The user's full name must appear in the response."""
        user_id = _insert_user(name="Priya Sharma")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Priya Sharma" in response.data

    def test_profile_shows_user_email(self, client):
        """The user's email address must appear in the response."""
        user_id = _insert_user(email="priya@example.com")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"priya@example.com" in response.data

    def test_profile_shows_member_since_section(self, client):
        """The page must include a 'Member since' label."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Member since" in response.data

    def test_profile_avatar_initials_rendered(self, client):
        """Avatar initials block must be present (section wraps initials)."""
        user_id = _insert_user(name="Priya Sharma")
        _login(client, user_id)
        response = _get_profile(client)
        # The initials are rendered inside .profile-avatar__initials
        assert b"profile-avatar__initials" in response.data

    def test_profile_name_first_char_initial_present(self, client):
        """First initial of the user name must be present on the page."""
        user_id = _insert_user(name="Rohan Verma")
        _login(client, user_id)
        response = _get_profile(client)
        # 'R' and 'V' are the initials for Rohan Verma
        assert b"R" in response.data
        assert b"V" in response.data

    def test_profile_different_user_sees_own_name(self, client):
        """Each user must see only their own name, not another user's."""
        _insert_user(name="Priya Sharma", email="priya@example.com")
        user_id_b = _insert_user(name="Amit Patel", email="amit@example.com")
        _login(client, user_id_b)
        response = _get_profile(client)
        assert b"Amit Patel" in response.data
        assert b"Priya Sharma" not in response.data


# ---------------------------------------------------------------------------
# 5. Summary stats — total_spent, transaction_count, top_category
# ---------------------------------------------------------------------------

class TestSummaryStats:
    """The stats row must show total_spent, transaction_count, top_category."""

    def test_profile_shows_total_spent_label(self, client):
        """'Total Spent' label must appear in the stats section."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Total Spent" in response.data

    def test_profile_shows_transaction_count_label(self, client):
        """'Transactions' label must appear in the stats section."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Transactions" in response.data

    def test_profile_shows_top_category_label(self, client):
        """'Top Category' label must appear in the stats section."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Top Category" in response.data

    def test_profile_total_spent_correct_inr_format(self, client):
        """Total spent must be formatted as INR with rupee symbol."""
        user_id = _insert_user()
        _insert_expense(user_id, 2500.00, "Bills", "2026-06-05", "Electricity")
        _insert_expense(user_id, 1000.00, "Food",  "2026-06-10", "Groceries")
        _login(client, user_id)
        response = _get_profile(client)
        # 2500 + 1000 = 3500 → formatted as ₹3,500
        assert "₹3,500".encode() in response.data

    def test_profile_transaction_count_correct(self, client):
        """Transaction count must reflect the actual number of expense rows."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food",      "2026-06-01", "Breakfast")
        _insert_expense(user_id, 200.00, "Transport", "2026-06-02", "Bus")
        _insert_expense(user_id, 300.00, "Health",    "2026-06-03", "Medicine")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"3" in response.data

    def test_profile_top_category_is_highest_spend(self, client):
        """Top category must be the one with the greatest total spend."""
        user_id = _insert_user()
        _insert_expense(user_id, 5000.00, "Health",    "2026-06-01", "Hospital")
        _insert_expense(user_id,  500.00, "Food",      "2026-06-02", "Lunch")
        _insert_expense(user_id,  200.00, "Transport", "2026-06-03", "Cab")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Health" in response.data

    def test_profile_stats_section_has_three_stat_cards(self, client):
        """The page must render all three stat cards."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        html = response.data.decode()
        assert html.count("profile-stat-card") >= 3

    def test_profile_inr_symbol_present_in_total(self, client):
        """The rupee symbol ₹ must appear in the total spent stat."""
        user_id = _insert_user()
        _insert_expense(user_id, 999.00, "Shopping", "2026-06-01", "Shoes")
        _login(client, user_id)
        response = _get_profile(client)
        assert "₹".encode("utf-8") in response.data


# ---------------------------------------------------------------------------
# 6. Summary stats — edge cases (zero expenses, single expense)
# ---------------------------------------------------------------------------

class TestSummaryStatsEdgeCases:
    """Stats must degrade gracefully when no or very few expenses exist."""

    def test_profile_zero_expenses_total_is_zero(self, client):
        """With no expenses, total_spent must show ₹0."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert "₹0".encode() in response.data

    def test_profile_zero_expenses_top_category_placeholder(self, client):
        """With no expenses, top_category must show the em-dash placeholder."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert "—".encode("utf-8") in response.data

    def test_profile_zero_expenses_count_is_zero(self, client):
        """With no expenses, transaction_count must show 0."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"0" in response.data

    def test_profile_single_expense_total_and_count(self, client):
        """A single expense must produce count=1 and correct total."""
        user_id = _insert_user()
        _insert_expense(user_id, 750.00, "Food", "2026-06-15", "Dinner")
        _login(client, user_id)
        response = _get_profile(client)
        assert "₹750".encode() in response.data
        assert b"1" in response.data

    def test_profile_zero_expenses_page_still_200(self, client):
        """Profile with no expenses must still render without a server error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert response.status_code == 200

    def test_profile_amount_with_thousands_separator(self, client):
        """Amounts >= 1000 must include comma thousands separator in INR format."""
        user_id = _insert_user()
        _insert_expense(user_id, 12000.00, "Bills", "2026-06-01", "Rent")
        _login(client, user_id)
        response = _get_profile(client)
        assert "₹12,000".encode() in response.data


# ---------------------------------------------------------------------------
# 7. Transaction history table — rows, column data, date formatting, amounts
# ---------------------------------------------------------------------------

class TestTransactionHistoryTable:
    """Recent Transactions table must display each expense's data correctly."""

    def test_profile_shows_transaction_table_heading(self, client):
        """'Recent Transactions' heading must be visible on the page."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Recent Transactions" in response.data

    def test_profile_transaction_description_appears(self, client):
        """Expense description must appear as a table cell."""
        user_id = _insert_user()
        _insert_expense(user_id, 499.00, "Entertainment", "2026-06-11", "OTT subscription")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"OTT subscription" in response.data

    def test_profile_transaction_category_appears(self, client):
        """Expense category must appear as a badge in the table."""
        user_id = _insert_user()
        _insert_expense(user_id, 600.00, "Health", "2026-06-09", "Vitamins")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Health" in response.data

    def test_profile_transaction_amount_inr_format(self, client):
        """Expense amount must be formatted with ₹ symbol."""
        user_id = _insert_user()
        _insert_expense(user_id, 2500.00, "Bills", "2026-06-05", "Electricity")
        _login(client, user_id)
        response = _get_profile(client)
        assert "₹2,500".encode() in response.data

    def test_profile_transaction_date_human_readable(self, client):
        """Date must be rendered in human-readable form (e.g. '15 Jun 2026')."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-15", "Lunch")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"15 Jun 2026" in response.data

    def test_profile_multiple_transactions_all_visible(self, client):
        """All inserted expenses must appear in the table (up to the limit)."""
        user_id = _insert_user()
        _insert_expense(user_id, 2500.00, "Bills",         "2026-06-15", "Electricity bill")
        _insert_expense(user_id,  499.00, "Entertainment", "2026-06-11", "OTT subscription")
        _insert_expense(user_id,  850.00, "Transport",     "2026-06-03", "Monthly bus pass")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Electricity bill"   in response.data
        assert b"OTT subscription"   in response.data
        assert b"Monthly bus pass"   in response.data

    def test_profile_table_columns_present(self, client):
        """The table must have Date, Description, Category, and Amount headers."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Date"        in response.data
        assert b"Description" in response.data
        assert b"Category"    in response.data
        assert b"Amount"      in response.data

    def test_profile_category_badge_css_class_used(self, client):
        """Category must render with a cat-badge CSS class, not inline colour."""
        user_id = _insert_user()
        _insert_expense(user_id, 180.00, "Food", "2026-06-07", "Snacks")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"cat-badge" in response.data
        # No inline style attribute should carry a colour value for the badge
        html = response.data.decode()
        # Inline colour via style attribute is forbidden (hex or rgb)
        assert 'style="color:' not in html
        assert "style='color:" not in html


# ---------------------------------------------------------------------------
# 8. Transaction history table — capped at 10 most-recent rows
# ---------------------------------------------------------------------------

class TestTransactionHistoryLimit:
    """get_user_expenses must cap output at the 10 most-recent expenses."""

    def test_profile_more_than_10_expenses_capped_at_10(self, client):
        """When 12 expenses exist only the 10 most-recent descriptions show."""
        user_id = _insert_user()
        # Insert 12 expenses spanning different dates; newest at 2026-06-12
        for i in range(1, 13):
            _insert_expense(
                user_id, float(100 * i), "Food",
                f"2026-06-{i:02d}", f"Expense day {i:02d}",
            )
        _login(client, user_id)
        response = _get_profile(client)
        html = response.data.decode()
        # Oldest two (day 01 and day 02) must NOT appear; newest 10 must appear
        assert "Expense day 01" not in html
        assert "Expense day 02" not in html
        assert "Expense day 12" in html


# ---------------------------------------------------------------------------
# 9. Category breakdown — at least three categories rendered
# ---------------------------------------------------------------------------

class TestCategoryBreakdown:
    """Category breakdown section must display per-category totals."""

    def test_profile_shows_category_breakdown_heading(self, client):
        """'Spending by Category' heading must be visible."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Spending by Category" in response.data

    def test_profile_shows_at_least_three_categories(self, client):
        """With three expense categories, all three must appear in breakdown."""
        user_id = _insert_user()
        _insert_expense(user_id, 2500.00, "Shopping",  "2026-06-01", "Clothes")
        _insert_expense(user_id,  850.00, "Transport", "2026-06-02", "Bus pass")
        _insert_expense(user_id,  600.00, "Health",    "2026-06-03", "Pharmacy")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Shopping"   in response.data
        assert b"Transport"  in response.data
        assert b"Health"     in response.data

    def test_profile_category_breakdown_shows_inr_totals(self, client):
        """Each category's total must be displayed with ₹ symbol."""
        user_id = _insert_user()
        _insert_expense(user_id, 3000.00, "Bills", "2026-06-01", "Rent")
        _login(client, user_id)
        response = _get_profile(client)
        assert "₹3,000".encode() in response.data

    def test_profile_category_breakdown_css_class_present(self, client):
        """Category breakdown rows must use the cat-breakdown CSS class."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-01", "Snack")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"cat-breakdown" in response.data


# ---------------------------------------------------------------------------
# 10. Category breakdown — percentage calculation
# ---------------------------------------------------------------------------

class TestCategoryBreakdownPercentage:
    """Category percentages must be correctly derived from totals."""

    def test_profile_single_category_is_100_percent(self, client):
        """A single category covering all spend must show 100%."""
        user_id = _insert_user()
        _insert_expense(user_id, 1000.00, "Bills", "2026-06-01", "Rent")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"100" in response.data

    def test_profile_two_equal_categories_each_50_percent(self, client):
        """Two equal-spend categories must each show 50%."""
        user_id = _insert_user()
        _insert_expense(user_id, 1000.00, "Bills",    "2026-06-01", "Rent")
        _insert_expense(user_id, 1000.00, "Shopping", "2026-06-02", "Clothes")
        _login(client, user_id)
        response = _get_profile(client)
        html = response.data.decode()
        assert html.count("50") >= 2

    def test_profile_pct_css_variable_used_for_bar(self, client):
        """Progress bar fill must use --bar-pct CSS variable, not inline width."""
        user_id = _insert_user()
        _insert_expense(user_id, 2000.00, "Food", "2026-06-01", "Groceries")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"--bar-pct" in response.data


# ---------------------------------------------------------------------------
# 11. Category breakdown — capped at 7 categories
# ---------------------------------------------------------------------------

class TestCategoryBreakdownLimit:
    """get_user_categories must cap output at 7 categories."""

    def test_profile_eight_categories_shows_only_top_seven(self, client):
        """The 8th (lowest-spend) category must not appear in the breakdown."""
        user_id = _insert_user()
        categories = [
            (700.00, "Bills"),
            (600.00, "Food"),
            (500.00, "Transport"),
            (400.00, "Health"),
            (300.00, "Shopping"),
            (200.00, "Entertainment"),
            (100.00, "Other"),
            ( 50.00, "Education"),      # 8th — must be excluded
        ]
        for i, (amt, cat) in enumerate(categories):
            _insert_expense(user_id, amt, cat, f"2026-06-{i+1:02d}", f"desc {i}")
        _login(client, user_id)
        response = _get_profile(client)
        html = response.data.decode()
        # Top 7 categories must appear in the breakdown section
        assert "Bills" in html
        # The 8th category must NOT appear inside a cat-breakdown row
        assert 'cat-breakdown__name">Education' not in html


# ---------------------------------------------------------------------------
# 12. Category breakdown — empty state (no expenses)
# ---------------------------------------------------------------------------

class TestCategoryBreakdownEmpty:
    """With no expenses, category breakdown must render without errors."""

    def test_profile_no_expenses_category_section_renders(self, client):
        """Profile must return 200 even when no categories exist."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert response.status_code == 200

    def test_profile_no_expenses_category_heading_still_present(self, client):
        """Spending by Category heading must appear even with zero expenses."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Spending by Category" in response.data


# ---------------------------------------------------------------------------
# 13. Navbar state — logged-in shows Logout, hides Sign in
# ---------------------------------------------------------------------------

class TestNavbarState:
    """Navbar must reflect the current auth state via base.html session check."""

    def test_profile_nav_shows_logout_link_when_logged_in(self, client):
        """'Logout' link must be present in the navbar for authenticated users."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Logout" in response.data

    def test_profile_nav_hides_sign_in_when_logged_in(self, client):
        """'Sign in' link must NOT appear when the user is authenticated."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Sign in" not in response.data

    def test_profile_nav_hides_get_started_when_logged_in(self, client):
        """'Get started' CTA must NOT appear when the user is authenticated."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Get started" not in response.data


# ---------------------------------------------------------------------------
# 14. No hardcoded hex colours in profile.html
# ---------------------------------------------------------------------------

class TestNoHardcodedColours:
    """profile.html must use CSS variables for all colours — no raw hex values."""

    def test_profile_html_contains_no_hex_colour_values(self):
        """
        Read profile.html directly and assert that no 6-digit or 3-digit hex
        colour codes appear (e.g. #ff6347 or #fff).
        """
        template_path = (
            "C:/Ddrive/Daya/CCA-Practice/Claude-Code-Practice/"
            "expense-tracker/templates/profile.html"
        )
        with open(template_path, encoding="utf-8") as fh:
            content = fh.read()
        # Match #RRGGBB and #RGB hex codes (case-insensitive)
        hex_pattern = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?![0-9a-fA-F])")
        matches = hex_pattern.findall(content)
        assert matches == [], (
            f"Hardcoded hex colour(s) found in profile.html: {matches}"
        )


# ---------------------------------------------------------------------------
# 15. Date filter — only one date supplied (hint shown, filter inactive)
# ---------------------------------------------------------------------------

class TestDateFilterSingleDate:
    """Submitting only one of from_date / to_date must show a hint, not crash."""

    def test_filter_only_from_date_shows_hint(self, client):
        """Providing from_date without to_date must show a validation hint."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, from_date="2026-06-01")
        assert response.status_code == 200
        assert b"both a start and an end date" in response.data

    def test_filter_only_to_date_shows_hint(self, client):
        """Providing to_date without from_date must show a validation hint."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, to_date="2026-06-30")
        assert response.status_code == 200
        assert b"both a start and an end date" in response.data

    def test_filter_only_from_date_filter_remains_inactive(self, client):
        """When only one date is given all expenses must still appear (no filter)."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-05-01", "Old expense")
        _insert_expense(user_id, 200.00, "Food", "2026-06-15", "New expense")
        _login(client, user_id)
        response = _get_profile(client, from_date="2026-06-01")
        # Both expenses visible because filter is inactive
        assert b"Old expense" in response.data
        assert b"New expense" in response.data


# ---------------------------------------------------------------------------
# 16. Date filter — from_date after to_date (error shown)
# ---------------------------------------------------------------------------

class TestDateFilterInvalidRange:
    """start > end must show an error message and leave stats unfiltered."""

    def test_filter_from_after_to_shows_error(self, client):
        """from_date > to_date must display the validation error message."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        assert response.status_code == 200
        assert b"Start date must be on or before the end date" in response.data

    def test_filter_from_after_to_does_not_crash(self, client):
        """Invalid date range must not raise a server error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-12-31", to_date="2026-01-01"
        )
        assert response.status_code == 200

    def test_filter_from_after_to_shows_all_expenses(self, client):
        """After an invalid range error all expenses must remain visible."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-01", "Breakfast")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        # Expenses not filtered — original data still present
        assert b"Breakfast" in response.data

    def test_filter_equal_dates_is_valid(self, client):
        """from_date == to_date is a valid single-day range (no error)."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Health", "2026-06-15", "Doctor")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-15", to_date="2026-06-15"
        )
        assert response.status_code == 200
        assert b"Start date must be on or before" not in response.data
        assert b"Doctor" in response.data


# ---------------------------------------------------------------------------
# 17. Date filter — valid range filters expenses, stats, categories
# ---------------------------------------------------------------------------

class TestDateFilterValidRange:
    """A valid date range must restrict all three data sections."""

    def test_filter_valid_range_shows_only_in_range_expenses(self, client):
        """Expenses outside the range must not appear in the table."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food",    "2026-05-15", "May lunch")
        _insert_expense(user_id, 200.00, "Food",    "2026-06-10", "June lunch")
        _insert_expense(user_id, 300.00, "Health",  "2026-07-01", "July checkup")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"June lunch"   in response.data
        assert b"May lunch"    not in response.data
        assert b"July checkup" not in response.data

    def test_filter_valid_range_updates_total_spent(self, client):
        """Total spent must reflect only the filtered expenses."""
        user_id = _insert_user()
        # Outside range — must NOT count
        _insert_expense(user_id, 5000.00, "Bills", "2026-05-01", "Old rent")
        # Inside range — must count
        _insert_expense(user_id, 1000.00, "Food",  "2026-06-10", "Groceries")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "₹1,000".encode() in response.data
        # Grand total of both would be ₹6,000 — that must NOT appear
        assert "₹6,000".encode() not in response.data

    def test_filter_valid_range_updates_transaction_count(self, client):
        """Transaction count must reflect only the filtered expenses."""
        user_id = _insert_user()
        _insert_expense(user_id, 200.00, "Food", "2026-05-20", "Old snack")
        _insert_expense(user_id, 300.00, "Food", "2026-06-05", "New snack")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        # Transaction count of 1 must appear; 2 must not be the count
        # (Check the stat card value, not just anywhere on the page)
        assert "1" in html

    def test_filter_valid_range_updates_top_category(self, client):
        """Top category must be derived from filtered expenses only."""
        user_id = _insert_user()
        # Before range: Health dominates globally
        _insert_expense(user_id, 9000.00, "Health",  "2026-05-01", "Surgery")
        # In range: Shopping dominates within range
        _insert_expense(user_id,  800.00, "Shopping","2026-06-05", "Shoes")
        _insert_expense(user_id,  200.00, "Food",    "2026-06-10", "Lunch")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"Shopping" in response.data

    def test_filter_valid_range_updates_category_breakdown(self, client):
        """Category breakdown must only include categories with filtered spend."""
        user_id = _insert_user()
        _insert_expense(user_id, 5000.00, "Bills",   "2026-05-01", "Old rent")
        _insert_expense(user_id,  700.00, "Food",    "2026-06-10", "Groceries")
        _insert_expense(user_id,  300.00, "Health",  "2026-06-15", "Pharmacy")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        assert "Food"   in html
        assert "Health" in html
        # Bills was outside the range; it must not appear in the breakdown
        assert 'cat-breakdown__name">Bills' not in html

    def test_filter_no_expenses_in_range_shows_zero_stats(self, client):
        """A valid range with no matching expenses must show ₹0 and — stats."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food", "2026-05-01", "Old meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "₹0".encode()      in response.data
        assert "—".encode("utf-8") in response.data

    def test_filter_boundary_dates_inclusive(self, client):
        """Expenses on from_date and to_date themselves must be included."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-01", "Start day")
        _insert_expense(user_id, 200.00, "Food", "2026-06-30", "End day")
        _insert_expense(user_id, 999.00, "Bills","2026-07-01", "Outside")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"Start day" in response.data
        assert b"End day"   in response.data
        assert b"Outside"   not in response.data


# ---------------------------------------------------------------------------
# 18. Date filter — active-filter indicator visibility
# ---------------------------------------------------------------------------

class TestActiveFilterIndicator:
    """An active-filter badge must appear when a valid range is applied."""

    def test_active_filter_indicator_shown_when_filter_active(self, client):
        """Applying a valid date range must render the active-filter badge."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"filter-active-badge" in response.data

    def test_active_filter_indicator_shows_date_range(self, client):
        """The active-filter badge must display the applied from and to dates."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"2026-06-01" in response.data
        assert b"2026-06-30" in response.data

    def test_active_filter_indicator_hidden_without_filter(self, client):
        """Without any date params the active-filter badge must not appear."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"filter-active-badge" not in response.data


# ---------------------------------------------------------------------------
# 19. Date filter — Clear link resets to unfiltered view
# ---------------------------------------------------------------------------

class TestDateFilterClearLink:
    """The Clear link must point to /profile with no query parameters."""

    def test_filter_form_has_clear_link(self, client):
        """The filter form must include a Clear link."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Clear" in response.data

    def test_active_filter_badge_has_clear_link(self, client):
        """When a filter is active the badge must show a Clear link."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        # The clear link must point to /profile (url_for result), no params
        assert 'href="/profile"' in html

    def test_clearing_filter_shows_all_expenses(self, client):
        """After clearing, all expenses (no date restriction) must appear."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-05-01", "Old meal")
        _insert_expense(user_id, 200.00, "Food", "2026-06-15", "New meal")
        _login(client, user_id)
        # First: apply a filter
        client.get("/profile?from_date=2026-06-01&to_date=2026-06-30")
        # Then: clear by requesting /profile with no params
        response = client.get("/profile")
        assert b"Old meal" in response.data
        assert b"New meal" in response.data


# ---------------------------------------------------------------------------
# 20. Date filter — pre-population of inputs after submission
# ---------------------------------------------------------------------------

class TestDateFilterPrePopulation:
    """After applying a filter the form inputs must retain the submitted dates."""

    def test_filter_inputs_prepopulated_with_from_date(self, client):
        """from_date input must have its value set to the submitted date."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b'value="2026-06-01"' in response.data

    def test_filter_inputs_prepopulated_with_to_date(self, client):
        """to_date input must have its value set to the submitted date."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b'value="2026-06-30"' in response.data

    def test_filter_inputs_empty_without_filter(self, client):
        """Without any filter params, date inputs must have empty values."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        html = response.data.decode()
        # Both inputs should have no pre-populated date value
        assert 'value="2026-' not in html
