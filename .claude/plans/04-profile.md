# Plan: Profile Page (Step 4)

## Context
Spec: `.claude/specs/04-profile.md`
Goal: Replace the `/profile` stub route with a fully designed, session-gated profile page
showing **hardcoded** data. No DB queries in this step — the UI is built first so the layout
can be validated before the backend wiring step.

---

## Files changed / created

| File | Action |
|---|---|
| `app.py` | Replace stub `/profile` route (lines 96–98) |
| `templates/profile.html` | Create — 4-section profile page |
| `static/css/profile.css` | Create — page-specific styles, BEM, CSS vars only |
| `tests/test_profile.py` | Create — 13 tests, session + content assertions |

---

## Step 1 — `app.py`: Route replacement

Guard: `if not session.get("user_id"): return redirect(url_for("login"))`

Hardcoded context passed to template:
- `user` — name, email, member_since
- `stats` — total_spent (₹6,374), transaction_count (8), top_category (Bills)
- `expenses` — 8 rows matching seed data (Bills, Shopping, Entertainment, Health, Food×2, Transport, Other)
- `categories` — 7 rows with name, total, pct (percentage for progress bar)

---

## Step 2 — `templates/profile.html`: 4-section layout

Extends `base.html`. Loads `profile.css` + Lucide Icons CDN via `{% block head %}`.

| Section | Content |
|---|---|
| 1 — User info card | Avatar initials, name, email, member-since date |
| 2 — Stats row | 3-column grid: Total Spent, Transactions, Top Category |
| 3 — Transaction table | Date / Description / Category badge / Amount (right-aligned) |
| 4 — Category breakdown | Name + total (flex) + 8px progress bar per category |

**Key Jinja2 patterns:**
- Initials: `{{ user.name.split()[0][0] }}{{ user.name.split()[-1][0] }}`
- Badge class: `cat-badge--{{ expense.category | lower | replace(' ', '-') }}`
- Progress bar width: `style="--bar-pct: {{ cat.pct }}%"` (CSS custom property, not colour)

---

## Step 3 — `static/css/profile.css`: BEM + CSS variables only

Zero hex values — every colour token uses `var(--...)` from `style.css`.

Key rules:
- `.profile-stats` — 3-column grid (1-column on mobile ≤768px)
- `.cat-badge--<category>` — 7 pill badge colour modifiers
- `.cat-breakdown__fill` — `width: var(--bar-pct)` — receives percentage from Jinja2
- `.cat-breakdown__fill--<category>` — 7 fill colour modifiers
- Responsive: hero stacks vertically, date column hidden, stats become 1 column

---

## Step 4 — `tests/test_profile.py`: 13 tests

Pattern matches `tests/test_login_logout.py` exactly:
- `_insert_user()` helper via `db_module.get_db()`
- `client.session_transaction()` to set `sess["user_id"]`

Tests cover: redirect without session, 200 with session, user name/email visible,
₹6,374 total, transaction_count, top category, 3 known transaction descriptions,
3 category names, logout link in nav, stale session_id (9999) still renders (Step 4
does not validate user_id against DB).

---

## Verification

```bash
pytest tests/test_profile.py -v   # new tests
pytest -v                          # full suite, no regressions

# Manual
python app.py
# → http://localhost:5001/profile without login → redirects to /login
# → login → lands on /profile with all 4 sections
# → DevTools: no hex values in profile.html or profile.css
```

---

## Definition of done
- [x] `/profile` without session → redirect to `/login`
- [x] `/profile` with session → HTTP 200
- [x] User info card shows name and email
- [x] 3 summary stat values visible
- [x] Transaction table has 8 rows
- [x] Category breakdown has 7 categories
- [x] Navbar shows Logout (logged-in state)
- [x] Zero hex colour values in `profile.html`
- [x] `pytest` passes with no failures
