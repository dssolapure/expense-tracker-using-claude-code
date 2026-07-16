# Implementation Plan: Delete Functionality (Step 09)

## Overview
Replace the stub `GET /expenses/<int:id>/delete` route with a `POST`-only handler.
Destructive operations must never use GET — a GET-based delete can be triggered by
browser prefetch, history traversal, or link crawlers. The delete button in the
profile expense table is a mini `<form method="POST">` — no JavaScript required.
`get_expense_by_id` (already in `db.py` from Step 08) is reused for the 404/403 check.

---

## Task sequence

### Task 1 — Update `database/db.py`: add `delete_expense` helper

Append after `update_expense` (after line 214):

```python
def delete_expense(expense_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
```

Single parameterised DELETE. No return value needed — the route already verified
ownership before calling this.

---

### Task 2 — Update `app.py`

#### 2a — Extend the import from `database/db.py` (lines 5–10)

Add `delete_expense` to the existing import:

```python
from database.db import (
    get_db, init_db, seed_db, create_user, get_user_by_email,
    get_user_by_id, _fmt_date, _fmt_member_since,
    get_user_expenses, get_user_stats, get_user_categories,
    add_expense, get_expense_by_id, update_expense, delete_expense,
)
```

#### 2b — Replace the stub route (lines 300–302)

**Remove:**
```python
@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"
```

**Replace with:**
```python
@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense_view(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id)
    if expense is None:
        abort(404)
    if expense["user_id"] != session["user_id"]:
        abort(403)

    delete_expense(id)
    return redirect(url_for("profile"))
```

**Important naming note:** the route function must be named `delete_expense_view`
(not `delete_expense`) because `delete_expense` is now the imported DB helper.
The `url_for()` call in the template uses the function name — update it to
`url_for('delete_expense_view', id=expense.id)`.

---

### Task 3 — Update `templates/profile.html`

The Actions column (lines 131–133) currently contains only the Edit link:

```html
<td class="txn-table__td txn-table__td--actions">
  <a href="{{ url_for('edit_expense', id=expense.id) }}" class="txn-edit-link">Edit</a>
</td>
```

Add a Delete form alongside the Edit link:

```html
<td class="txn-table__td txn-table__td--actions">
  <a href="{{ url_for('edit_expense', id=expense.id) }}" class="txn-edit-link">Edit</a>
  <form method="POST"
        action="{{ url_for('delete_expense_view', id=expense.id) }}"
        class="txn-delete-form">
    <button type="submit" class="txn-delete-btn">Delete</button>
  </form>
</td>
```

Key points:
- The `<form>` has `method="POST"` — never use `<a>` for destructive actions
- `action` uses `url_for('delete_expense_view', id=expense.id)` — matches the new function name
- Both Edit link and Delete form sit inside the same `<td>` — displayed side by side via flexbox

---

### Task 4 — Update `static/css/profile.css`

Append at the bottom of the existing file:

```css
/* ── Delete button ───────────────────────────────────────────────── */

.txn-delete-form {
    display: inline;
    margin: 0;
    padding: 0;
}

.txn-delete-btn {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--danger);
    background: transparent;
    border: 1px solid var(--danger);
    border-radius: var(--radius-sm);
    padding: 0.2rem 0.5rem;
    cursor: pointer;
    line-height: normal;
}

.txn-delete-btn:hover {
    background: var(--danger);
    color: var(--paper);
}
```

The Actions `<td>` already has `white-space: nowrap` and `text-align: right` from
Step 08 — no changes needed to `.txn-table__td--actions`.

Update `.txn-table__td--actions` to use flexbox so Edit and Delete sit side by side:

```css
.txn-table__td--actions {
    text-align: right;
    white-space: nowrap;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.4rem;
}
```

> `var(--danger)` must already exist in `style.css` — check before using. If missing,
> use `var(--accent)` as fallback and note that a `--danger` variable needs adding.

---

## Implementation order

1 → 2 → 3 → 4  
DB helper first, then route, then template, then CSS.

---

## File change summary

| File | Action |
|---|---|
| `database/db.py` | Add `delete_expense(expense_id)` helper |
| `app.py` | Extend import; replace stub with POST-only `delete_expense_view` |
| `templates/profile.html` | Add Delete `<form>` in Actions column per expense row |
| `static/css/profile.css` | Append `.txn-delete-form`, `.txn-delete-btn` styles; update `.txn-table__td--actions` to flexbox |

No new files created.

---

## Validation checklist (maps to Definition of Done)

- [ ] `POST /expenses/<id>/delete` logged out → redirect to `/login`
- [ ] `POST /expenses/999/delete` (non-existent) → 404
- [ ] `POST /expenses/<other-user-expense-id>/delete` → 403
- [ ] `POST /expenses/<id>/delete` valid → row deleted, redirect to `/profile`
- [ ] Deleted expense no longer appears in the profile expense list
- [ ] Stats card (total spent, transaction count, top category) updates after delete
- [ ] Category breakdown updates after delete
- [ ] Each expense row has a working Delete button
- [ ] Delete button submits via POST (not a GET link)
- [ ] All form actions use `url_for()` — no hardcoded URLs
- [ ] `pytest` passes with no regressions
