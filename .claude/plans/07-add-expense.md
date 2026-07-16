# Implementation Plan: Add Expense (Step 07)

## Overview
Replace the stub `GET /expenses/add` route with a full GET+POST handler backed by a
new `add_expense` DB helper, a new form template, and an "+ Add Expense" link on the
profile page. No schema changes needed — the `expenses` table already exists from
Step 05.

---

## Task sequence

### Task 1 — Update `database/db.py`: add `add_expense` helper

Append after `get_user_by_id` (before the formatting helpers):

```python
def add_expense(user_id, amount, category, date, description):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description or None),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id
```

Key points:
- Parameterised query only — no f-strings or `.format()` in SQL
- `description or None` converts an empty string to SQL `NULL`
- Returns the new row's `id` (useful for tests and future features)

---

### Task 2 — Update `app.py`

#### 2a — Add `EXPENSE_CATEGORIES` constant

Define once at module level, after `app.secret_key` and before
`with app.app_context()`:

```python
EXPENSE_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]
```

This list is passed to the template — never hardcoded in HTML.

#### 2b — Extend the import from `database/db.py`

Add `add_expense` to the existing import block:

```python
from database.db import (
    get_db, init_db, seed_db, create_user, get_user_by_email,
    get_user_by_id, _fmt_date, _fmt_member_since,
    get_user_expenses, get_user_stats, get_user_categories,
    add_expense,
)
```

#### 2c — Replace the stub route with GET+POST handler

```python
@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense_view():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=EXPENSE_CATEGORIES,
            form={},
        )

    # --- POST ---
    amount_raw  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    date        = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    form = {"amount": amount_raw, "category": category,
            "date": date, "description": description}

    def fail(msg):
        return render_template(
            "add_expense.html",
            categories=EXPENSE_CATEGORIES,
            error=msg,
            form=form,
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

    if not date:
        return fail("Date is required.")
    if not _DATE_RE.match(date):
        return fail("Invalid date. Use YYYY-MM-DD format.")

    add_expense(session["user_id"], amount, category, date, description)
    return redirect(url_for("profile"))
```

Design notes:
- Auth guard first — both GET and POST redirect unauthenticated users to `/login`
- `form={}` on GET means all `form.x` references in the template silently return empty string (no `KeyError`)
- `form` dict rebuilt from submitted values on POST so they survive a validation failure
- Inner `fail()` helper avoids repeating `render_template` at every validation branch
- Validation order: amount → category → date (matches form field order top-to-bottom)
- `_DATE_RE` (module-level regex) validates `YYYY-MM-DD` format
- On success: `redirect(url_for("profile"))` — never re-render the form

---

### Task 3 — Create `templates/add_expense.html`

Extends `base.html`. Loads `add_expense.css`. Single `<form>` with four fields:

```html
{% extends "base.html" %}
{% block head %}
  <link rel="stylesheet" href="{{ url_for('static', filename='css/add_expense.css') }}">
{% endblock %}

{% block content %}
<div class="add-expense-page">
  <div class="add-expense-card">
    <h1 class="add-expense-title">Add Expense</h1>

    {% if error %}
      <div class="auth-error">{{ error }}</div>
    {% endif %}

    <form method="POST" action="{{ url_for('add_expense_view') }}">
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

      <button type="submit" class="btn-submit">Save Expense</button>
    </form>

    <a href="{{ url_for('profile') }}" class="add-expense-back">← Back to profile</a>
  </div>
</div>
{% endblock %}
```

Key points:
- `{% if form.category == cat %}selected{% endif %}` — preserves dropdown selection after validation failure
- Form action uses `url_for('add_expense_view')` — no hardcoded URLs
- Global `form-group`, `form-input`, `btn-submit` classes come from `style.css`

---

### Task 4 — Create `static/css/add_expense.css`

Page-specific styles only. CSS variables — no hardcoded hex values:

```css
.add-expense-page {
  min-height: 80vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 3rem 1rem;
  background: var(--paper);
}

.add-expense-card {
  width: 100%;
  max-width: var(--auth-width);
  background: var(--paper-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 2rem 2.5rem;
}

.add-expense-title {
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

.add-expense-back {
  display: block;
  margin-top: 1.25rem;
  font-size: 0.875rem;
  color: var(--ink-muted);
  text-decoration: none;
}

.add-expense-back:hover {
  color: var(--ink);
}
```

---

### Task 5 — Modify `templates/profile.html`

Add an "+ Add Expense" button in the transaction section header. The
`profile-section__header` div wraps the heading and the new button side-by-side:

```html
<div class="profile-section__header">
  <h2 class="profile-section__heading">
    <i data-lucide="clock" class="profile-icon"></i>
    Recent Transactions
  </h2>
  <a href="{{ url_for('add_expense_view') }}" class="btn-primary">+ Add Expense</a>
</div>
```

`btn-primary` is already defined in `style.css` — no new CSS needed.

---

## Implementation order

1 → 2 → 3 → 4 → 5  
DB helper first (so route can import it), then route, then template + CSS, then
profile link last.

---

## File change summary

| File | Action |
|---|---|
| `database/db.py` | Add `add_expense()` helper |
| `app.py` | Add `EXPENSE_CATEGORIES`; extend import; replace stub with GET+POST handler |
| `templates/add_expense.html` | **Create** — expense entry form |
| `static/css/add_expense.css` | **Create** — page-specific styles |
| `templates/profile.html` | Modify — add "+ Add Expense" link in transaction section header |

---

## Validation checklist (maps to Definition of Done)

- [ ] `GET /expenses/add` logged out → redirect to `/login`
- [ ] `GET /expenses/add` logged in → form renders with all fields empty
- [ ] POST valid data → row inserted in `expenses`, redirect to `/profile`
- [ ] New expense appears at top of profile expense list
- [ ] POST blank amount → validation error; other fields preserved
- [ ] POST amount = 0 or negative → validation error
- [ ] POST invalid date format → validation error
- [ ] POST category not in allowed list → validation error
- [ ] POST blank description → success; `NULL` stored in DB
- [ ] "+ Add Expense" link on profile navigates to `/expenses/add`
- [ ] All form links and actions use `url_for()` — no hardcoded URLs
- [ ] `pytest` passes with no regressions
