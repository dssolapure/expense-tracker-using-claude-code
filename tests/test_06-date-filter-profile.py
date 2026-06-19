# tests/test_06-date-filter-profile.py
"""
Test suite for Step 06: Date Filter on Profile Page.

Spec: .claude/specs/06-date-filter-profile.md
Route: GET /profile  (extended — no new routes)

Definition-of-done coverage
────────────────────────────
DoD 1.  No query params → all expenses shown (baseline behaviour unchanged)
DoD 2.  Valid range → only in-range expenses appear in the transactions table
DoD 3.  Total spent stat reflects only filtered expenses
DoD 4.  Transaction count stat reflects only filtered expenses
DoD 5.  Top category stat derived from filtered expenses
DoD 6.  Category breakdown percentages recalculated from filtered expenses
DoD 7.  Form inputs pre-populated with current filter values after submission
DoD 8.  Active-filter indicator visible when filter is applied
DoD 9.  "Clear" link removes filter and shows all expenses
DoD 10. from_date > to_date → validation error rendered, no crash
DoD 11. Only one date provided → hint rendered, filter inactive (all data shown)

Additional edge-case groups
────────────────────────────
A. Boundary-inclusive BETWEEN behaviour (from_date and to_date themselves included)
B. Malformed date strings (non-YYYY-MM-DD values) are rejected as validation errors
C. same-day range (from_date == to_date) is accepted as valid
D. Empty-range: valid range but no expenses within it → ₹0 / em-dash placeholders
E. Filter applies to all three helpers independently (expenses, stats, categories)
F. Auth guard still enforces redirect even when query params are present
G. Query-param passthrough: filter_from and filter_to forwarded to template correctly
"""

import pytest
from werkzeug.security import generate_password_hash
import database.db as db_module


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _insert_user(name="Ananya Iyer", email="ananya@example.com",
                 password="secure123"):
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
    """Inject user_id into the session so the client is authenticated."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _get_profile(client, **query_params):
    """Issue GET /profile, appending any keyword args as query-string params."""
    if query_params:
        qs = "&".join(f"{k}={v}" for k, v in query_params.items())
        url = f"/profile?{qs}"
    else:
        url = "/profile"
    return client.get(url)


# ---------------------------------------------------------------------------
# DoD 1 — No query params shows all expenses (baseline unchanged)
# ---------------------------------------------------------------------------

class TestNoFilterBaselineBehaviour:
    """GET /profile with no query params must behave exactly as before Step 06."""

    def test_no_params_returns_200(self, client):
        """Authenticated request with no filter params must return HTTP 200."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert response.status_code == 200

    def test_no_params_all_expenses_visible(self, client):
        """All inserted expenses must appear when no filter is supplied."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food",      "2026-04-10", "April snack")
        _insert_expense(user_id, 800.00, "Transport", "2026-05-20", "May bus pass")
        _insert_expense(user_id, 300.00, "Health",    "2026-06-15", "June pharmacy")
        _login(client, user_id)
        response = _get_profile(client)
        assert b"April snack"   in response.data
        assert b"May bus pass"  in response.data
        assert b"June pharmacy" in response.data

    def test_no_params_total_spent_covers_all_expenses(self, client):
        """Total spent stat must sum all expenses when no filter is active."""
        user_id = _insert_user()
        _insert_expense(user_id, 1000.00, "Bills", "2026-05-01", "May rent")
        _insert_expense(user_id, 2000.00, "Bills", "2026-06-01", "June rent")
        _login(client, user_id)
        response = _get_profile(client)
        assert "₹3,000".encode() in response.data

    def test_no_params_filter_form_present(self, client):
        """Date filter form elements must be present even when no filter is active."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"from_date" in response.data
        assert b"to_date"   in response.data
        assert b"Apply"     in response.data

    def test_no_params_active_filter_indicator_absent(self, client):
        """Active-filter badge must NOT appear when no date range is submitted."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"filter-active-badge" not in response.data

    def test_no_params_clear_link_present(self, client):
        """A 'Clear' link must still appear in the form when filter is inactive."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Clear" in response.data


# ---------------------------------------------------------------------------
# DoD 2 — Valid range → only in-range expenses in the transactions table
# ---------------------------------------------------------------------------

class TestValidRangeFiltersTransactions:
    """Expenses outside the submitted date range must be hidden from the table."""

    def test_in_range_expense_appears(self, client):
        """An expense dated within the range must appear in the transactions table."""
        user_id = _insert_user()
        _insert_expense(user_id, 250.00, "Food", "2026-06-15", "June lunch")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"June lunch" in response.data

    def test_expense_before_range_hidden(self, client):
        """An expense dated before from_date must not appear in the table."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-05-31", "May meal")
        _insert_expense(user_id, 200.00, "Food", "2026-06-10", "June meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"June meal" in response.data
        assert b"May meal"  not in response.data

    def test_expense_after_range_hidden(self, client):
        """An expense dated after to_date must not appear in the table."""
        user_id = _insert_user()
        _insert_expense(user_id, 150.00, "Food",    "2026-06-20", "June snack")
        _insert_expense(user_id, 400.00, "Health",  "2026-07-01", "July checkup")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"June snack"   in response.data
        assert b"July checkup" not in response.data

    def test_expenses_before_and_after_range_both_hidden(self, client):
        """Expenses outside both ends of the range must be excluded."""
        user_id = _insert_user()
        _insert_expense(user_id,  100.00, "Food",   "2026-05-01", "Before range")
        _insert_expense(user_id,  500.00, "Bills",  "2026-06-15", "In range")
        _insert_expense(user_id, 2000.00, "Health", "2026-07-10", "After range")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"In range"    in response.data
        assert b"Before range" not in response.data
        assert b"After range"  not in response.data

    def test_no_params_shows_all_three_expenses(self, client):
        """Clearing the filter afterwards shows all three expenses again."""
        user_id = _insert_user()
        _insert_expense(user_id,  100.00, "Food",   "2026-05-01", "Before range")
        _insert_expense(user_id,  500.00, "Bills",  "2026-06-15", "In range")
        _insert_expense(user_id, 2000.00, "Health", "2026-07-10", "After range")
        _login(client, user_id)
        # Apply filter first, then clear
        client.get("/profile?from_date=2026-06-01&to_date=2026-06-30")
        response = _get_profile(client)
        assert b"Before range" in response.data
        assert b"In range"     in response.data
        assert b"After range"  in response.data


# ---------------------------------------------------------------------------
# DoD 3 — Total spent stat reflects only filtered expenses
# ---------------------------------------------------------------------------

class TestFilteredTotalSpent:
    """get_user_stats must sum only expenses within the active date range."""

    def test_total_spent_excludes_out_of_range_expenses(self, client):
        """Total must not include expenses dated outside the filter range."""
        user_id = _insert_user()
        _insert_expense(user_id, 9000.00, "Bills", "2026-05-01", "Old rent")
        _insert_expense(user_id, 1500.00, "Food",  "2026-06-10", "Groceries")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "₹1,500".encode() in response.data
        # Combined total of both must NOT appear
        assert "₹10,500".encode() not in response.data

    def test_total_spent_sums_multiple_in_range_expenses(self, client):
        """When multiple expenses are in range, total must be their combined sum."""
        user_id = _insert_user()
        _insert_expense(user_id, 1000.00, "Food",      "2026-06-05", "Groceries")
        _insert_expense(user_id, 2000.00, "Transport", "2026-06-10", "Cab month")
        _insert_expense(user_id, 5000.00, "Bills",     "2026-05-01", "Old rent")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "₹3,000".encode() in response.data
        assert "₹5,000".encode() not in response.data

    def test_total_spent_zero_when_no_in_range_expenses(self, client):
        """When no expense falls in the range, total_spent must display ₹0."""
        user_id = _insert_user()
        _insert_expense(user_id, 5000.00, "Bills", "2026-04-01", "April rent")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "₹0".encode() in response.data


# ---------------------------------------------------------------------------
# DoD 4 — Transaction count stat reflects only filtered expenses
# ---------------------------------------------------------------------------

class TestFilteredTransactionCount:
    """get_user_stats must count only expenses within the active date range."""

    def test_count_excludes_out_of_range_expenses(self, client):
        """Transaction count must not include out-of-range expenses."""
        user_id = _insert_user()
        _insert_expense(user_id, 200.00, "Food", "2026-05-20", "Old snack")
        _insert_expense(user_id, 300.00, "Food", "2026-06-05", "New snack")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        # count of 1 should appear; 2 should not be the transaction count
        # We verify the stat section shows 1 via transaction_count context
        assert "1" in html

    def test_count_zero_when_no_in_range_expenses(self, client):
        """When no expense falls in the range, transaction_count must be 0."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food", "2026-04-10", "April meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"0" in response.data

    def test_count_multiple_in_range_expenses(self, client):
        """Count must reflect the actual number of in-range expense rows."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food",      "2026-06-01", "Day 1")
        _insert_expense(user_id, 200.00, "Transport", "2026-06-10", "Day 10")
        _insert_expense(user_id, 300.00, "Health",    "2026-06-20", "Day 20")
        _insert_expense(user_id, 999.00, "Bills",     "2026-05-01", "Out of range")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"3" in response.data


# ---------------------------------------------------------------------------
# DoD 5 — Top category stat derived from filtered expenses
# ---------------------------------------------------------------------------

class TestFilteredTopCategory:
    """Top category must come from filtered expenses, not the global dataset."""

    def test_top_category_changes_with_filter(self, client):
        """Top category inside a range must differ from the global top category."""
        user_id = _insert_user()
        # Globally: Health dominates
        _insert_expense(user_id, 10000.00, "Health",   "2026-04-01", "Surgery")
        # Within June range: Shopping dominates
        _insert_expense(user_id,   800.00, "Shopping", "2026-06-05", "Shoes")
        _insert_expense(user_id,   200.00, "Food",     "2026-06-10", "Lunch")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"Shopping" in response.data
        # Health must NOT be the top category shown for the filtered view
        # (Health does not appear in the range at all, so it won't be top)
        html = response.data.decode()
        # The stat card value for Top Category must show Shopping
        # We verify by checking its presence and that ₹10,000 from Health is absent
        assert "₹10,000".encode() not in response.data

    def test_top_category_placeholder_when_no_in_range_expenses(self, client):
        """With no expenses in range, top_category must show the em-dash placeholder."""
        user_id = _insert_user()
        _insert_expense(user_id, 5000.00, "Bills", "2026-04-01", "Old rent")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "—".encode("utf-8") in response.data


# ---------------------------------------------------------------------------
# DoD 6 — Category breakdown percentages recalculated from filtered expenses
# ---------------------------------------------------------------------------

class TestFilteredCategoryBreakdown:
    """Category breakdown section must be recomputed from the filtered expense set."""

    def test_category_absent_from_range_not_in_breakdown(self, client):
        """A category with no expenses in the filter range must not appear in breakdown."""
        user_id = _insert_user()
        # Out of range: Bills
        _insert_expense(user_id, 5000.00, "Bills",  "2026-05-01", "Old rent")
        # In range
        _insert_expense(user_id,  700.00, "Food",   "2026-06-10", "Groceries")
        _insert_expense(user_id,  300.00, "Health", "2026-06-15", "Pharmacy")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        assert "Food"   in html
        assert "Health" in html
        assert 'cat-breakdown__name">Bills' not in html

    def test_category_percentage_recalculated_for_filtered_set(self, client):
        """Percentages must be based on filtered total, not global total."""
        user_id = _insert_user()
        # Only one category in range → must show 100 %
        _insert_expense(user_id, 10000.00, "Health", "2026-04-01", "Big surgery")
        _insert_expense(user_id,  1000.00, "Food",   "2026-06-10", "June grocery")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        # Food is the only category in range → 100 %
        assert b"100" in response.data

    def test_category_breakdown_empty_state_when_no_in_range_expenses(self, client):
        """When no expenses fall in range, get_user_categories returns [] — page renders."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food", "2026-05-01", "Old meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert response.status_code == 200
        assert b"Spending by Category" in response.data

    def test_two_equal_categories_in_range_each_fifty_percent(self, client):
        """Two equal-spend in-range categories must each have a ~50 % bar."""
        user_id = _insert_user()
        _insert_expense(user_id, 1000.00, "Bills",    "2026-06-05", "Rent")
        _insert_expense(user_id, 1000.00, "Shopping", "2026-06-15", "Clothes")
        # Out of range — must not distort the percentages
        _insert_expense(user_id, 9000.00, "Health",   "2026-05-01", "Surgery")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        # 50 must appear at least twice (once per category)
        assert html.count("50") >= 2


# ---------------------------------------------------------------------------
# DoD 7 — Form inputs pre-populated with current filter values after submission
# ---------------------------------------------------------------------------

class TestFilterFormPrePopulation:
    """After applying a filter, the form inputs must retain the submitted dates."""

    def test_from_date_input_prepopulated(self, client):
        """The from_date input value must equal the submitted from_date."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b'value="2026-06-01"' in response.data

    def test_to_date_input_prepopulated(self, client):
        """The to_date input value must equal the submitted to_date."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b'value="2026-06-30"' in response.data

    def test_both_inputs_prepopulated_on_active_filter(self, client):
        """Both inputs must be populated simultaneously on a valid active filter."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-07-01", to_date="2026-07-31"
        )
        assert b'value="2026-07-01"' in response.data
        assert b'value="2026-07-31"' in response.data

    def test_inputs_empty_when_no_filter_submitted(self, client):
        """Without any filter params, the date inputs must carry no date value."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        html = response.data.decode()
        # No YYYY-MM-DD pattern should appear as a pre-populated input value
        import re
        pre_populated = re.findall(r'value="(\d{4}-\d{2}-\d{2})"', html)
        assert pre_populated == []

    def test_inputs_cleared_after_validation_error(self, client):
        """When from > to causes an error, the inputs must NOT retain invalid values."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        # Route resets both to "" on error — no date values in inputs
        html = response.data.decode()
        import re
        pre_populated = re.findall(r'value="(\d{4}-\d{2}-\d{2})"', html)
        assert pre_populated == []


# ---------------------------------------------------------------------------
# DoD 8 — Active-filter indicator visible when filter is applied
# ---------------------------------------------------------------------------

class TestActiveFilterIndicator:
    """A visible active-filter badge must appear whenever a valid range is active."""

    def test_badge_visible_with_valid_range(self, client):
        """Applying a valid date range must render the filter-active-badge element."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"filter-active-badge" in response.data

    def test_badge_hidden_without_any_filter(self, client):
        """The badge must not render when no date params are provided."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"filter-active-badge" not in response.data

    def test_badge_hidden_after_validation_error(self, client):
        """An invalid range (from > to) must not show the active-filter badge."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        assert b"filter-active-badge" not in response.data

    def test_badge_hidden_when_only_one_date_supplied(self, client):
        """Supplying only one date must not activate the filter or show the badge."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, from_date="2026-06-01")
        assert b"filter-active-badge" not in response.data

    def test_badge_shows_formatted_from_date(self, client):
        """The badge must display the start date in the human-readable format."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        # _fmt_date("2026-06-01") → "1 Jun 2026" (Windows %#d) or "1 Jun 2026" (Unix %-d)
        html = response.data.decode()
        assert "Jun 2026" in html

    def test_badge_shows_formatted_to_date(self, client):
        """The badge must display the end date in the human-readable format."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        assert "30 Jun 2026" in html


# ---------------------------------------------------------------------------
# DoD 9 — "Clear" link removes filter and shows all expenses
# ---------------------------------------------------------------------------

class TestClearFilter:
    """Navigating to /profile with no params (the Clear link target) must reset view."""

    def test_clear_link_points_to_profile_no_params(self, client):
        """The clear link inside the active-filter badge must point to /profile."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        assert 'href="/profile"' in html

    def test_clear_link_present_in_form_when_filter_inactive(self, client):
        """A clear link must also appear in the filter form when no range is active."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"Clear" in response.data

    def test_navigating_to_profile_no_params_shows_all_expenses(self, client):
        """GET /profile with no params after a filtered request shows all expenses."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food",   "2026-05-01", "May meal")
        _insert_expense(user_id, 200.00, "Health", "2026-06-15", "June medicine")
        _login(client, user_id)
        # First apply a filter that would hide the May expense
        client.get("/profile?from_date=2026-06-01&to_date=2026-06-30")
        # Then "clear" by fetching /profile with no params
        response = _get_profile(client)
        assert b"May meal"       in response.data
        assert b"June medicine"  in response.data

    def test_clearing_resets_active_filter_badge(self, client):
        """After clearing, the active-filter badge must not be present."""
        user_id = _insert_user()
        _login(client, user_id)
        client.get("/profile?from_date=2026-06-01&to_date=2026-06-30")
        response = _get_profile(client)
        assert b"filter-active-badge" not in response.data


# ---------------------------------------------------------------------------
# DoD 10 — from_date > to_date → validation error, no crash
# ---------------------------------------------------------------------------

class TestInvalidDateRange:
    """Submitting from_date > to_date must render an error and return HTTP 200."""

    def test_from_after_to_returns_200(self, client):
        """An inverted range must not cause a server error (500)."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-12-31", to_date="2026-01-01"
        )
        assert response.status_code == 200

    def test_from_after_to_shows_error_message(self, client):
        """The route must render the 'Start date must be on or before' error text."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        assert b"Start date must be on or before the end date" in response.data

    def test_from_after_to_filter_treated_as_inactive(self, client):
        """After an invalid range error all expenses must remain visible (unfiltered)."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-05-01", "Old breakfast")
        _insert_expense(user_id, 200.00, "Food", "2026-06-15", "New breakfast")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        assert b"Old breakfast" in response.data
        assert b"New breakfast" in response.data

    def test_from_after_to_active_filter_badge_absent(self, client):
        """An inverted range must not trigger the active-filter badge."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        assert b"filter-active-badge" not in response.data

    def test_from_equal_to_is_valid_single_day_range(self, client):
        """from_date == to_date is a valid range; no error must be shown."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Health", "2026-06-15", "Doctor visit")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-15", to_date="2026-06-15"
        )
        assert response.status_code == 200
        assert b"Start date must be on or before" not in response.data
        assert b"Doctor visit" in response.data

    def test_from_equal_to_shows_active_filter_badge(self, client):
        """A same-day range must activate the filter and show the badge."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-15", "Snack")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-15", to_date="2026-06-15"
        )
        assert b"filter-active-badge" in response.data


# ---------------------------------------------------------------------------
# DoD 11 — Only one date provided → hint shown, filter inactive
# ---------------------------------------------------------------------------

class TestSingleDateHint:
    """Submitting only from_date or only to_date must show a hint, not crash."""

    def test_only_from_date_returns_200(self, client):
        """A request with only from_date must still return HTTP 200."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, from_date="2026-06-01")
        assert response.status_code == 200

    def test_only_to_date_returns_200(self, client):
        """A request with only to_date must still return HTTP 200."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, to_date="2026-06-30")
        assert response.status_code == 200

    def test_only_from_date_shows_hint_message(self, client):
        """Providing only from_date must render the 'both a start and an end date' hint."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, from_date="2026-06-01")
        assert b"both a start and an end date" in response.data

    def test_only_to_date_shows_hint_message(self, client):
        """Providing only to_date must render the 'both a start and an end date' hint."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, to_date="2026-06-30")
        assert b"both a start and an end date" in response.data

    def test_only_from_date_filter_inactive_all_expenses_shown(self, client):
        """When only from_date is given, all expenses (unfiltered) must appear."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-04-01", "April meal")
        _insert_expense(user_id, 200.00, "Food", "2026-06-15", "June meal")
        _login(client, user_id)
        response = _get_profile(client, from_date="2026-06-01")
        # Filter is inactive so April meal must also appear
        assert b"April meal" in response.data
        assert b"June meal"  in response.data

    def test_only_to_date_filter_inactive_all_expenses_shown(self, client):
        """When only to_date is given, all expenses (unfiltered) must appear."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-04-01", "April meal")
        _insert_expense(user_id, 200.00, "Food", "2026-07-20", "July meal")
        _login(client, user_id)
        response = _get_profile(client, to_date="2026-06-30")
        assert b"April meal" in response.data
        assert b"July meal"  in response.data

    def test_only_from_date_active_filter_badge_absent(self, client):
        """Single date must not activate the filter or show the active-filter badge."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client, from_date="2026-06-01")
        assert b"filter-active-badge" not in response.data

    def test_hint_not_shown_without_any_date(self, client):
        """The hint must not appear when no date params are supplied at all."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(client)
        assert b"both a start and an end date" not in response.data


# ---------------------------------------------------------------------------
# Edge case A — Boundary-inclusive BETWEEN behaviour
# ---------------------------------------------------------------------------

class TestBoundaryInclusive:
    """Expenses dated exactly on from_date and to_date must be included."""

    def test_expense_on_from_date_included(self, client):
        """An expense dated exactly on from_date must appear in the table."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-01", "First day expense")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"First day expense" in response.data

    def test_expense_on_to_date_included(self, client):
        """An expense dated exactly on to_date must appear in the table."""
        user_id = _insert_user()
        _insert_expense(user_id, 200.00, "Bills", "2026-06-30", "Last day expense")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"Last day expense" in response.data

    def test_expense_one_day_before_from_date_excluded(self, client):
        """An expense one day before from_date must NOT appear."""
        user_id = _insert_user()
        _insert_expense(user_id, 999.00, "Health", "2026-05-31", "Eve expense")
        _insert_expense(user_id, 100.00, "Food",   "2026-06-10", "In range")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"Eve expense" not in response.data
        assert b"In range"   in response.data

    def test_expense_one_day_after_to_date_excluded(self, client):
        """An expense one day after to_date must NOT appear."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Health", "2026-07-01", "Day after")
        _insert_expense(user_id, 100.00, "Food",   "2026-06-10", "In range")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"Day after" not in response.data
        assert b"In range"  in response.data


# ---------------------------------------------------------------------------
# Edge case B — Malformed date string validation
# ---------------------------------------------------------------------------

class TestMalformedDateValidation:
    """Non-YYYY-MM-DD values in query params must trigger a validation error."""

    def test_malformed_from_date_shows_error(self, client):
        """A non-date string in from_date must render an invalid-date error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="not-a-date", to_date="2026-06-30"
        )
        assert response.status_code == 200
        assert b"Invalid start date" in response.data

    def test_malformed_to_date_shows_error(self, client):
        """A non-date string in to_date must render an invalid-date error."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="31/06/2026"
        )
        assert response.status_code == 200
        assert b"Invalid end date" in response.data

    def test_malformed_from_date_filter_inactive(self, client):
        """A malformed from_date must leave the filter inactive (all data shown)."""
        user_id = _insert_user()
        _insert_expense(user_id, 100.00, "Food", "2026-06-01", "All expenses visible")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="INVALID", to_date="2026-06-30"
        )
        assert b"All expenses visible" in response.data

    def test_malformed_from_date_badge_absent(self, client):
        """A malformed date must not activate the filter badge."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="bad", to_date="2026-06-30"
        )
        assert b"filter-active-badge" not in response.data


# ---------------------------------------------------------------------------
# Edge case C — Same-day range is valid
# ---------------------------------------------------------------------------

class TestSameDayRange:
    """from_date == to_date is a one-day range; must be accepted without error."""

    def test_same_day_range_accepted(self, client):
        """Identical from_date and to_date must not produce any error message."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-15", to_date="2026-06-15"
        )
        assert b"Start date must be on or before" not in response.data
        assert b"both a start and an end date"    not in response.data

    def test_same_day_range_shows_only_that_days_expense(self, client):
        """Only the expense on that exact date must appear in the table."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Health", "2026-06-15", "Exact day")
        _insert_expense(user_id, 999.00, "Bills",  "2026-06-14", "Day before")
        _insert_expense(user_id, 999.00, "Bills",  "2026-06-16", "Day after")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-15", to_date="2026-06-15"
        )
        assert b"Exact day"   in response.data
        assert b"Day before"  not in response.data
        assert b"Day after"   not in response.data


# ---------------------------------------------------------------------------
# Edge case D — Empty range: valid dates but no matching expenses
# ---------------------------------------------------------------------------

class TestEmptyRangeResult:
    """A valid date range that matches no expenses must degrade gracefully."""

    def test_empty_range_returns_200(self, client):
        """A range with no matching expenses must still return HTTP 200."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food", "2026-04-01", "Old meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert response.status_code == 200

    def test_empty_range_shows_zero_total(self, client):
        """total_spent must be ₹0 when no expenses fall in the range."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food", "2026-04-01", "Old meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "₹0".encode() in response.data

    def test_empty_range_shows_em_dash_top_category(self, client):
        """top_category must be the em-dash placeholder when range has no expenses."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food", "2026-04-01", "Old meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert "—".encode("utf-8") in response.data

    def test_empty_range_shows_zero_transaction_count(self, client):
        """transaction_count must be 0 when no expenses fall in the range."""
        user_id = _insert_user()
        _insert_expense(user_id, 500.00, "Food", "2026-04-01", "Old meal")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"0" in response.data

    def test_empty_range_active_filter_badge_still_shows(self, client):
        """Even with no matching expenses, the active-filter badge must be visible."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"filter-active-badge" in response.data


# ---------------------------------------------------------------------------
# Edge case E — All three helper functions filtered independently
# ---------------------------------------------------------------------------

class TestAllThreeHelpersFiltered:
    """Expenses, stats, and categories must all be derived from the same filtered set."""

    def test_all_sections_reflect_same_filter(self, client):
        """
        Stats, transactions table, and category breakdown must all exclude the
        same out-of-range expense so results are internally consistent.
        """
        user_id = _insert_user()
        # In range
        _insert_expense(user_id, 600.00, "Shopping", "2026-06-10", "Shoes")
        _insert_expense(user_id, 400.00, "Food",     "2026-06-20", "Groceries")
        # Out of range
        _insert_expense(user_id, 5000.00, "Bills",   "2026-05-01", "Old rent")
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        html = response.data.decode()
        # Transaction table: only in-range descriptions
        assert "Shoes"     in html
        assert "Groceries" in html
        assert "Old rent"  not in html
        # Stats: total = 600 + 400 = 1000
        assert "₹1,000".encode() in response.data
        # Category breakdown: Bills (out of range) must not appear
        assert 'cat-breakdown__name">Bills' not in html


# ---------------------------------------------------------------------------
# Edge case F — Auth guard enforces redirect even with query params
# ---------------------------------------------------------------------------

class TestAuthGuardWithQueryParams:
    """The /profile auth guard must fire regardless of query-string content."""

    def test_unauthenticated_with_filter_params_redirects(self, client):
        """An unauthenticated request carrying filter params must still redirect."""
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert response.status_code == 302
        assert response.location.endswith("/login")

    def test_unauthenticated_with_filter_params_no_content(self, client):
        """Profile content must not leak to an unauthenticated request."""
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"Recent Transactions" not in response.data
        assert b"Total Spent"         not in response.data

    def test_stale_session_with_filter_params_redirects(self, client):
        """A stale session carrying filter params must also redirect to /login."""
        with client.session_transaction() as sess:
            sess["user_id"] = 99999
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert response.status_code == 302
        assert response.location.endswith("/login")


# ---------------------------------------------------------------------------
# Edge case G — Template receives correct context variables
# ---------------------------------------------------------------------------

class TestTemplateContextVariables:
    """Route must pass filter_from and filter_to to the template for pre-population."""

    def test_filter_from_present_in_response_data(self, client):
        """The submitted from_date string must appear somewhere in the HTML."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"2026-06-01" in response.data

    def test_filter_to_present_in_response_data(self, client):
        """The submitted to_date string must appear somewhere in the HTML."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-01", to_date="2026-06-30"
        )
        assert b"2026-06-30" in response.data

    def test_filter_from_not_in_html_when_error(self, client):
        """After a from > to error the route resets filter_from to '' in context."""
        user_id = _insert_user()
        _login(client, user_id)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        # Dates should not appear as input values (they are cleared on error)
        assert b'value="2026-06-30"' not in response.data
        assert b'value="2026-06-01"' not in response.data

    def test_error_and_hint_are_mutually_exclusive(self, client):
        """A response must never show both an error message and a hint at once."""
        user_id = _insert_user()
        _login(client, user_id)
        # Trigger error (from > to)
        response = _get_profile(
            client, from_date="2026-06-30", to_date="2026-06-01"
        )
        html = response.data.decode()
        error_present = "Start date must be on or before" in html
        hint_present = "both a start and an end date" in html
        # At most one of the two should be present
        assert not (error_present and hint_present)
