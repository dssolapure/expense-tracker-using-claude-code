# Implementation Plan: Edit Expense (Step 08)

## Overview
Replace the stub `GET /expenses/<int:id>/edit` route with a full GET+POST handler.
The GET pre-fills a form with the expense's current values; the POST validates, updates
the DB row, and redirects to `/profile`. Ownership is enforced — a user may only edit
their own expenses. Unrecognised ids return 404; foreign-user ids return 403.

---

## Task sequence

### Task 1 — Update `database/db.py`

Three changes needed in this file.

#### 1a — Modify `get_user_expenses` to select and return `id`

The current SQL (line 136) selects only `date, description, category, amount`. Add
`id` so the profile template can build edit links.

**Change the SQL line:**
```python
# Before
sql = ("SELECT date, description, category, amount FROM expenses "
       "WHERE user_id = ?" + date_clause)

# After
sql = ("SELECT id, date, description, category, amount FROM expenses "
       "WHERE user_id = ?" + date_clause)
```

**Add `"id"` to the return dict (lines 143–150):**
```python
return [
    {
        "id": row["id"],
        "date": _fmt_date(row["date"]),
        "description": row["description"],
        "category": row["category"],
        "amount": _fmt_amount(row["amount"]),
    }
    for row in rows
]
```

> Backward-compatible — existing `expense.date`, `expense.category`, `expense.amount`,
> `expense.description` references in `profile.html` are unchanged.

#### 1b — Add `get_expense_by_id(expense_id)`

Append after `add_expense` (after line 192):

```python
def get_expense_by_id(expense_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    expense = cursor.fetchone()
    conn.close()
    return expense
```

Returns the full row (including `user_id` for the ownership check) or `None`.

#### 1c — Add `update_expense(expense_id, amount, category, date, description)`

Append after `get_expense_by_id`:

```python
def update_expense(expense_id, amount, category, date, description):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
        "WHERE id = ?",
        (amount, category, date, description or None, expense_id),
    )
    conn.commit()
    conn.close()
```

`description or None` converts an empty string to SQL `NULL`, consistent with
`add_expense`.

---

### Task 2 — Update `app.py`

#### 2a — Extend the import from `database/db.py` (lines 5–10)

```python
from database.db import (
    get_db, init_db, seed_db, create_user, get_user_by_email,
    get_user_by_id, _fmt_date, _fmt_member_since,
    get_user_expenses, get_user_stats, get_user_categories,
    add_expense, get_expense_by_id, update_expense,
)
```

#### 2b — Replace the stub `edit_expense` route (lines 236–238)

**Remove:**
```python
@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"
```

**Replace with:**
```python
@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id)
    if expense is None:
        abort(404)
    if expense["user_id"] != session["user_id"]:
        abort(403)

    if request.method == "GET":
        form = {
            "amount": expense["amount"],
            "category": expense["category"],
            "date": expense["date"],        # raw YYYY-MM-DD from DB — NOT formatted
            "description": expense["description"] or "",
        }
        return render_template(
            "edit_expense.html",
            categories=EXPENSE_CATEGORIES,
            form=form,
            expense_id=id,
        )

    # --- POST ---
    amount_raw  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    date_val    = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    form = {"amount": amount_raw, "category": category,
            "date": date_val, "description": description}

    def fail(msg):
        return render_template(
            "edit_expense.html",
            categories=EXPENSE_CATEGORIES,
            error=msg,
            form=form,
            expense_id=id,
        )

    if not amount_raw:
        return fail("Amount is required.")
    try:
        amount = float(amount_raw)
    except ValueError:
        return fail("Amount must be a number.")
    if amount <= 0:
        return fail("Amount must be greater than zero.")

    if category not in EXPENSE_CATEGORIES:
        return fail("Please select a valid category.")

    if not date_val:
        return fail("Date is required.")
    if not _DATE_RE.match(date_val):
        return fail("Invalid date. Use YYYY-MM-DD format.")

    update_expense(id, amount, category, date_val, description)
    return redirect(url_for("profile"))
```

**Critical notes:**
- Auth guard, 404, and 403 checks are at the top — both GET and POST are protected by
  the same block; no need to repeat per-method
- `form["date"]` on GET is set to `expense["date"]` — the raw `YYYY-MM-DD` string
  straight from SQLite. Do NOT call `_fmt_date()` here, as that produces a human-readable
  string ("1 Jun 2026") that the browser `<input type="date">` cannot parse, which was
  the root cause of the date-not-updating bug
- On POST failure, `form` is rebuilt from submitted values so the user sees what they
  typed, not the original DB values
- Local variable is `date_val` (not `date`) to avoid shadowing the `date` class
  imported from `datetime` at module level

---

### Task 3 — Create `templates/edit_expense.html`

Mirrors `add_expense.html` with three differences:
1. Page title/heading: "Edit Expense"
2. Form `action`: `url_for('edit_expense', id=expense_id)`
3. Submit button label: "Save Changes"

```html
{% extends "base.html" %}
{% block head %}
  <link rel="stylesheet" href="{{ url_for('static', filename='css/edit_expense.css') }}">
{% endblock %}

{% block content %}
<div class="edit-expense-page">
  <div class="edit-expense-card">
    <h1 class="edit-expense-title">Edit Expense</h1>

    {% if error %}
      <div class="auth-error">{{ error }}</div>
    {% endif %}

    <form method="POST" action="{{ url_for('edit_expense', id=expense_id) }}">
      <div class="form-group">
        <label for="amount">Amount (₹)</label>
        <input class="form-input" type="number" id="amount" name="amount"
               step="0.01" min="0.01" placeholder="0.00"
               value="{{ form.amount }}" required>
      </div>

      <div class="form-group">
        <label for="category">Category</label>
        <select class="form-input" id="category" name="category" required>
          <option value="">Select a category</option>
          {% for cat in categories %}
            <option value="{{ cat }}"
              {% if form.category == cat %}selected{% endif %}>
              {{ cat }}
            </option>
          {% endfor %}
        </select>
      </div>

      <div class="form-group">
        <label for="date">Date</label>
        <input class="form-input" type="date" id="date" name="date"
               value="{{ form.date }}" required>
      </div>

      <div class="form-group">
        <label for="description">Description <span class="optional">(optional)</span></label>
        <input class="form-input" type="text" id="description" name="description"
               placeholder="What was this for?"
               value="{{ form.description }}">
      </div>

      <button type="submit" class="btn-submit">Save Changes</button>
    </form>

    <a href="{{ url_for('profile') }}" class="edit-expense-back">← Back to profile</a>
  </div>
</div>
{% endblock %}
```

`form.amount` will be the raw float from SQLite on GET (e.g. `320.0`) — the number
input accepts this fine. `form.date` will be `"2026-06-01"` which is exactly the
format `<input type="date">` requires.

---

### Task 4 — Create `static/css/edit_expense.css`

Same layout as `add_expense.css` with `edit-expense-*` class names. CSS variables
only — no hardcoded hex values:

```css
.edit-expense-page {
  min-height: 80vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 3rem 1rem;
  background: var(--paper);
}

.edit-expense-card {
  width: 100%;
  max-width: var(--auth-width);
  background: var(--paper-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 2rem 2.5rem;
}

.edit-expense-title {
  font-family: var(--font-display);
  font-size: 1.75rem;
  color: var(--ink);
  margin-bottom: 1.5rem;
}

.optional {
  font-size: 0.8rem;
  color: var(--ink-faint);
  font-weight: 400;
}

.edit-expense-back {
  display: block;
  margin-top: 1.25rem;
  font-size: 0.875rem;
  color: var(--ink-muted);
  text-decoration: none;
}

.edit-expense-back:hover {
  color: var(--ink);
}
```

---

### Task 5 — Update `templates/profile.html`

Two targeted edits to the transaction table.

#### 5a — Add Actions column header to `<thead>`

Current `<thead>` (lines 111–116):
```html
<tr>
  <th class="txn-table__th">Date</th>
  <th class="txn-table__th">Description</th>
  <th class="txn-table__th">Category</th>
  <th class="txn-table__th txn-table__th--right">Amount</th>
</tr>
```

Add a fifth `<th>`:
```html
<tr>
  <th class="txn-table__th">Date</th>
  <th class="txn-table__th">Description</th>
  <th class="txn-table__th">Category</th>
  <th class="txn-table__th txn-table__th--right">Amount</th>
  <th class="txn-table__th txn-table__th--right">Actions</th>
</tr>
```

#### 5b — Add Edit link to each expense row

Current last `<td>` in the `{% for expense %}` loop (line 129–130):
```html
<td class="txn-table__td txn-table__td--amount">{{ expense.amount }}</td>
```

Append a fifth `<td>` after it:
```html
<td class="txn-table__td txn-table__td--amount">{{ expense.amount }}</td>
<td class="txn-table__td txn-table__td--actions">
  <a href="{{ url_for('edit_expense', id=expense.id) }}" class="txn-edit-link">Edit</a>
</td>
```

#### 5c — Append to `static/css/profile.css`

Add at the bottom of the existing file:

```css
/* ── Expense row actions ─────────────────────────────────────────── */

.txn-table__td--actions {
    text-align: right;
    white-space: nowrap;
}

.txn-edit-link {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--accent);
    text-decoration: none;
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--accent);
    border-radius: var(--radius-sm);
}

.txn-edit-link:hover {
    background: var(--accent);
    color: var(--paper);
}
```

---

## Implementation order

1 → 2 → 3 → 4 → 5  
DB helpers first (no UI dependency), then route (depends on helpers), then
template + CSS, then profile edits last (depends on `expense.id` being present).

---

## File change summary

| File | Action |
|---|---|
| `database/db.py` | Modify `get_user_expenses` (add `id`); add `get_expense_by_id()`; add `update_expense()` |
| `app.py` | Extend import; replace stub `edit_expense` with GET+POST handler |
| `templates/edit_expense.html` | **Create** — pre-filled edit form |
| `static/css/edit_expense.css` | **Create** — page-specific styles |
| `templates/profile.html` | Modify — add Actions column + Edit link per row |
| `static/css/profile.css` | Modify — append `.txn-edit-link` styles |

---

## Validation checklist (maps to Definition of Done)

- [ ] `GET /expenses/999/edit` → 404
- [ ] `GET /expenses/<other-user-expense-id>/edit` → 403
- [ ] `GET /expenses/<id>/edit` logged out → redirect `/login`
- [ ] `GET /expenses/<id>/edit` logged in → form pre-filled with correct values
- [ ] Date input shows the correct date in browser date picker (YYYY-MM-DD pre-fill)
- [ ] `POST` valid data → DB updated, redirect to `/profile`
- [ ] Changed date appears correctly in profile expense list after save
- [ ] `POST` blank amount → validation error, other fields preserved
- [ ] `POST` amount ≤ 0 → validation error
- [ ] `POST` invalid date → validation error
- [ ] `POST` invalid category → validation error
- [ ] `POST` blank description → success, `NULL` stored in DB
- [ ] Each expense row on profile has a working Edit link
- [ ] All links/actions use `url_for()` — no hardcoded URLs
- [ ] `pytest` passes with no regressions
