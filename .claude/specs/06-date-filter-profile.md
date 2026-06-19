1 # Spec: Date Filter on Profile
       2
       3 ## Overview
       4 Step 5 wired up all profile sections with live DB data. Step 6 adds a date-range filter to the profile page so users can narrow their transaction history, stats, and category breakdo
         wn to a specific period (e.g. "June 2026" or "last 30 days"). The filter is submitted as query-string parameters on `GET /profile`, keeping all logic server-side with no JavaScript r
         equired. This is the first interactive data-query feature in Spendly and establishes the pattern for filtering used in later steps.
       5
       6 ## Depends on
       7 - Step 1 — Database setup (`expenses` table with `date` column in `YYYY-MM-DD` format)
       8 - Step 2 — Registration (users must exist)
       9 - Step 3 — Login/logout (`user_id` stored in session)
      10 - Step 4 — Profile UI (`profile.html` with all four sections)
      11 - Step 5 — DB data on profile (all helper functions exist and are called from the route)
      12
      13 ## Routes
      14 No new routes. The existing `GET /profile` route is extended to read optional `from_date` and `to_date` query-string parameters and pass them through to the DB helpers and template.
      15
      16 ## Database changes
      17 No schema changes. The three existing helper functions are updated to accept optional date-range arguments:
      18 - `get_user_expenses(user_id, from_date=None, to_date=None)`
      19 - `get_user_stats(user_id, from_date=None, to_date=None)`
      20 - `get_user_categories(user_id, from_date=None, to_date=None)`
      21
      22 When both `from_date` and `to_date` are provided, each query appends `AND date BETWEEN ? AND ?`. When omitted, behaviour is identical to Step 5 (no date filtering).
      23
      24 ## Templates
      25 - **Modify:** `templates/profile.html`
      26   - Add a date-filter form above the Recent Transactions section
      27   - Form method `GET`, action `url_for('profile')`
      28   - Two `<input type="date">` fields: `from_date` and `to_date`
      29   - A "Apply" submit button and a "Clear" link that navigates back to `/profile` with no params
      30   - Pre-populate inputs with current filter values so the form remembers the user's selection
      31   - Show a visible indicator (e.g. banner or badge) when a filter is active
      32
      33 ## Files to change
      34 - `database/db.py` — add optional `from_date` / `to_date` parameters to `get_user_expenses()`, `get_user_stats()`, and `get_user_categories()`; build the WHERE clause conditionally u
         sing parameterised placeholders
      35 - `app.py` — read `request.args.get("from_date")` and `request.args.get("to_date")` in the `/profile` route; validate that if both are provided `from_date <= to_date`; pass them to e
         ach DB helper and forward them to the template as `filter_from` and `filter_to`
      36 - `templates/profile.html` — add the filter form and active-filter indicator as described above
      37 - `static/css/profile.css` — add styles for the filter form and active-filter badge (create this file if it does not already exist; otherwise append to it)
      38
      39 ## Files to create
      40 - `static/css/profile.css` — only if it does not already exist; contains filter form layout and badge styles using CSS variables
      41
      42 ## New dependencies
      43 No new dependencies.
      44
      45 ## Rules for implementation
      46 - No SQLAlchemy or ORMs — raw sqlite3 only
      47 - Parameterised queries only — never f-strings or string concatenation in SQL; use `?` placeholders for date values
      48 - Passwords hashed with werkzeug (no auth changes in this step)
      49 - Use CSS variables — never hardcode hex values in any `.css` or `.html` file
      50 - All templates extend `base.html`
      51 - Date validation in the route: if `from_date > to_date`, re-render the profile with an error message — do not crash or silently swap them
      52 - If only one of `from_date` / `to_date` is provided, treat the filter as inactive (ignore both) and show a validation hint in the UI
      53 - Never put date-comparison logic in the template — all filtering happens in Python/SQL
      54 - The "Clear" link must use `url_for('profile')` — never a hardcoded path
      55 - Stats and category breakdown must be recomputed from the filtered expense set, not cached from a previous full query
      56
      57 ## Definition of done
      58 - [ ] Visiting `/profile` with no query params shows all expenses (identical to Step 5 behaviour)
      59 - [ ] Submitting the filter form with a valid date range updates the Recent Transactions table to show only expenses within that range
      60 - [ ] Total spent stat reflects only the filtered expenses when a filter is active
      61 - [ ] Transaction count stat reflects only the filtered expenses when a filter is active
      62 - [ ] Top category stat is derived from filtered expenses when a filter is active
      63 - [ ] Category breakdown percentages are recalculated from filtered expenses
      64 - [ ] The filter form inputs are pre-populated with the current `from_date` and `to_date` values after submission
      65 - [ ] An active-filter indicator is visible when a date range is applied
      66 - [ ] Clicking "Clear" removes the filter and shows all expenses again
      67 - [ ] Submitting with `from_date > to_date` shows a validation error and does not crash
      68 - [ ] Submitting with only one date provided treats the filter as inactive and shows a hint
      