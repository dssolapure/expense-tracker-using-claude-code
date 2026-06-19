# Implementation Plan: Date Filter on Profile (Step 06)

## Overview
Add a server-side date-range filter to the profile page. Users submit `from_date` and `to_date` via a GET form; all three data sections (stats, transactions, categories) are recomputed from the filtered expense set.

---

## Task sequence

### Task 1 — Update `database/db.py` (3 functions)

All three helpers gain two optional keyword arguments: `from_date=None` and `to_date=None`.

When **both** are provided the WHERE clause gains `AND date BETWEEN ? AND ?` and the params tuple is extended accordingly. When either is `None` the query is unchanged.

**`get_user_expenses`**
```python
def get_user_expenses(user_id, from_date=None, to_date=None):
    conn = get_db()
    cursor = conn.cursor()
    sql = (
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ?"
    )
    params = [user_id]
    if from_date and to_date:
        sql += " AND date BETWEEN ? AND ?"
        params += [from_date, to_date]
    sql += " ORDER BY date DESC LIMIT 10"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "date": _fmt_date(row["date"]),
            "description": row["description"],
            "category": row["category"],
            "amount": _fmt_amount(row["amount"]),
        }
        for row in rows
    ]
```

**`get_user_stats`** — same pattern; extend both the main aggregate query and the top-category subquery with the BETWEEN clause.

```python
def get_user_stats(user_id, from_date=None, to_date=None):
    conn = get_db()
    cursor = conn.cursor()
    date_clause = " AND date BETWEEN ? AND ?" if (from_date and to_date) else ""
    date_params = [from_date, to_date] if (from_date and to_date) else []

    cursor.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
        f"FROM expenses WHERE user_id = ?{date_clause}",
        [user_id] + date_params,
    )
    row = cursor.fetchone()
    total_float, count = row["total"], row["cnt"]

    cursor.execute(
        f"SELECT category, SUM(amount) AS cat_total FROM expenses "
        f"WHERE user_id = ?{date_clause} GROUP BY category "
        f"ORDER BY cat_total DESC LIMIT 1",
        [user_id] + date_params,
    )
    top_row = cursor.fetchone()
    conn.close()
    return {
        "total_spent": _fmt_amount(total_float) if count > 0 else "₹0",
        "transaction_count": count,
        "top_category": top_row["category"] if top_row else "—",
    }
```

**`get_user_categories`** — same BETWEEN injection for both the grand-total query and the per-category group query.

```python
def get_user_categories(user_id, from_date=None, to_date=None):
    conn = get_db()
    cursor = conn.cursor()
    date_clause = " AND date BETWEEN ? AND ?" if (from_date and to_date) else ""
    date_params = [from_date, to_date] if (from_date and to_date) else []

    cursor.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS grand_total FROM expenses "
        f"WHERE user_id = ?{date_clause}",
        [user_id] + date_params,
    )
    grand_total = cursor.fetchone()["grand_total"]
    if grand_total == 0:
        conn.close()
        return []

    cursor.execute(
        f"SELECT category, SUM(amount) AS cat_total FROM expenses "
        f"WHERE user_id = ?{date_clause} GROUP BY category "
        f"ORDER BY cat_total DESC LIMIT 7",
        [user_id] + date_params,
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "name": row["category"],
            "total": _fmt_amount(row["cat_total"]),
            "pct": round(row["cat_total"] / grand_total * 100),
        }
        for row in rows
    ]
```

> **Note on SQL building:** the `date_clause` string is a fixed literal — never interpolated from user input — so this is safe from SQL injection. All user-supplied values flow through `?` placeholders.

---

### Task 2 — Update `app.py` `/profile` route

Read and validate the query-string parameters, then thread them through to all three DB helpers and into the template context.

```python
@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db_user = get_user_by_id(session["user_id"])
    if db_user is None:
        session.clear()
        return redirect(url_for("login"))

    user = {
        "name": db_user["name"],
        "email": db_user["email"],
        "member_since": _fmt_member_since(db_user["created_at"]),
    }

    # --- Date filter ---
    filter_from = request.args.get("from_date", "").strip()
    filter_to   = request.args.get("to_date", "").strip()
    filter_error = None
    filter_hint  = None
    active_filter = False

    # Only one date provided → treat as inactive, show hint
    if bool(filter_from) != bool(filter_to):
        filter_hint  = "Please provide both a start and an end date."
        filter_from  = filter_to = ""
    elif filter_from and filter_to:
        if filter_from > filter_to:
            filter_error = "Start date must be on or before the end date."
            filter_from  = filter_to = ""
        else:
            active_filter = True

    from_arg = filter_from if active_filter else None
    to_arg   = filter_to   if active_filter else None

    expenses   = get_user_expenses(session["user_id"], from_arg, to_arg)
    stats      = get_user_stats(session["user_id"], from_arg, to_arg)
    categories = get_user_categories(session["user_id"], from_arg, to_arg)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        expenses=expenses,
        categories=categories,
        filter_from=filter_from,
        filter_to=filter_to,
        active_filter=active_filter,
        filter_error=filter_error,
        filter_hint=filter_hint,
    )
```

Also update the import line at the top to include `request` (it's already imported) — no change needed.

---

### Task 3 — Update `templates/profile.html`

Insert the filter block **between** Section 2 (stats row) and the `profile-bottom-grid`. The filter block contains:

1. A `<form>` with method `GET` and `action="{{ url_for('profile') }}"`
2. Two `<input type="date">` fields pre-populated with `filter_from` and `filter_to`
3. An "Apply" submit button
4. A "Clear" anchor linking to `url_for('profile')` (no query params)
5. Conditional error/hint message rendered above the form
6. A visible active-filter badge rendered when `active_filter` is true

Insertion point in `profile.html` — after the closing `</section>` of `.profile-stats` and before `<div class="profile-bottom-grid">`:

```html
<!-- Section 2.5 — Date filter -->
{% if filter_error %}
<p class="filter-msg filter-msg--error">{{ filter_error }}</p>
{% elif filter_hint %}
<p class="filter-msg filter-msg--hint">{{ filter_hint }}</p>
{% endif %}

{% if active_filter %}
<div class="filter-active-badge">
  <i data-lucide="filter" class="profile-icon"></i>
  Showing {{ filter_from }} — {{ filter_to }}
  <a href="{{ url_for('profile') }}" class="filter-active-badge__clear">Clear</a>
</div>
{% endif %}

<form class="filter-form" method="GET" action="{{ url_for('profile') }}">
  <div class="filter-form__fields">
    <label class="filter-form__label" for="from_date">From</label>
    <input class="filter-form__input" type="date" id="from_date" name="from_date"
           value="{{ filter_from }}">
    <label class="filter-form__label" for="to_date">To</label>
    <input class="filter-form__input" type="date" id="to_date" name="to_date"
           value="{{ filter_to }}">
  </div>
  <div class="filter-form__actions">
    <button class="filter-form__btn" type="submit">Apply</button>
    {% if not active_filter %}
    <a class="filter-form__clear" href="{{ url_for('profile') }}">Clear</a>
    {% endif %}
  </div>
</form>
```

---

### Task 4 — Update `static/css/profile.css`

Append new rules at the bottom of the existing file (no existing rules need changing):

```css
/* ── Date filter form ────────────────────────────────────────────── */

.filter-form {
    background: var(--paper-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1rem 1.5rem;
    display: flex;
    align-items: flex-end;
    gap: 1rem;
    flex-wrap: wrap;
}

.filter-form__fields {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.filter-form__label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--ink-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.filter-form__input {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.4rem 0.75rem;
    font-size: 0.9rem;
    color: var(--ink);
    background: var(--paper);
}

.filter-form__input:focus {
    outline: none;
    border-color: var(--accent);
}

.filter-form__actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
}

.filter-form__btn {
    padding: 0.45rem 1.1rem;
    background: var(--accent);
    color: var(--paper);
    border: none;
    border-radius: var(--radius-sm);
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
}

.filter-form__btn:hover {
    opacity: 0.88;
}

.filter-form__clear {
    font-size: 0.85rem;
    color: var(--ink-muted);
    text-decoration: none;
}

.filter-form__clear:hover {
    color: var(--ink);
}

/* ── Active filter badge ─────────────────────────────────────────── */

.filter-active-badge {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--accent-light);
    border: 1px solid var(--accent);
    border-radius: var(--radius-sm);
    padding: 0.45rem 1rem;
    font-size: 0.85rem;
    color: var(--accent);
    font-weight: 500;
}

.filter-active-badge__clear {
    margin-left: auto;
    font-size: 0.8rem;
    color: var(--accent);
    text-decoration: underline;
    cursor: pointer;
}

/* ── Filter messages ─────────────────────────────────────────────── */

.filter-msg {
    padding: 0.6rem 1rem;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
}

.filter-msg--error {
    background: var(--danger-light);
    color: var(--danger);
    border: 1px solid var(--danger);
}

.filter-msg--hint {
    background: var(--paper-warm);
    color: var(--ink-muted);
    border: 1px solid var(--border);
}
```

---

## File change summary

| File | Action |
|---|---|
| `database/db.py` | Modify `get_user_expenses`, `get_user_stats`, `get_user_categories` — add optional `from_date`/`to_date` params |
| `app.py` | Modify `/profile` route — read, validate, and thread date filter params |
| `templates/profile.html` | Modify — insert filter form, active-filter badge, and error/hint messages |
| `static/css/profile.css` | Modify — append filter form and badge styles |

No new files are created (profile.css already exists).

---

## Validation checklist (maps to Definition of Done)

- [ ] `GET /profile` with no params → all expenses shown, form inputs empty
- [ ] `GET /profile?from_date=2026-06-01&to_date=2026-06-10` → only expenses in range shown; stats and categories recalculated
- [ ] Form inputs retain submitted values after apply
- [ ] Active-filter badge visible when filter is applied
- [ ] "Clear" link removes filter and shows all data
- [ ] `from_date > to_date` → validation error rendered, no crash
- [ ] Only one date provided → hint rendered, filter treated as inactive
- [ ] `pytest` passes with no new failures
