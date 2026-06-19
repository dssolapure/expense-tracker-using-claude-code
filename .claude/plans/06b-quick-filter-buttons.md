# Plan: Step 06b — Quick-Filter Shortcut Buttons

## Context
Step 06 implemented the manual date-range filter (from_date / to_date inputs + Apply button).
The spec overview also calls for quick-filter shortcut links — All Time, This Month,
Last 3 Months, Last 6 Months — beside the date filter form. These were not built in
the original step 06 implementation. This plan adds them server-side with no new packages.

---

## Approach
Server-side link generation: compute the date ranges in `app.py` and pass them as
template variables. Each shortcut is an `<a>` tag pointing to
`url_for('profile', from_date=..., to_date=...)`. "All Time" clears both params.
No JavaScript required (matches spec constraint).

Date arithmetic uses only the Python standard library (`datetime.date`, `timedelta`).

---

## Files to change

| File | What changes |
|------|-------------|
| `app.py` | Import `date, timedelta`; compute 4 date-range dicts; pass to profile template |
| `templates/profile.html` | Add quick-filter button row above the date filter form |
| `static/css/profile.css` | Add styles for `.quick-filter` row |

---

## Step 1 — `app.py`

Add to imports (top of file):
```python
from datetime import date, timedelta
```

Inside `profile()`, before `return render_template(...)`, compute shortcuts:
```python
_today = date.today()
quick_filters = {
    "This Month":    (_today.replace(day=1).isoformat(), _today.isoformat()),
    "Last 3 Months": ((_today - timedelta(days=90)).isoformat(), _today.isoformat()),
    "Last 6 Months": ((_today - timedelta(days=180)).isoformat(), _today.isoformat()),
}
```

Pass to template:
```python
return render_template(
    "profile.html",
    ...,
    quick_filters=quick_filters,
)
```

---

## Step 2 — `templates/profile.html`

Add a quick-filter row immediately above the existing `<form class="filter-form">`:

```html
<div class="quick-filter">
  <a href="{{ url_for('profile') }}"
     class="quick-filter__btn {% if not active_filter %}quick-filter__btn--active{% endif %}">
    All Time
  </a>
  {% for label, (from_d, to_d) in quick_filters.items() %}
  <a href="{{ url_for('profile', from_date=from_d, to_date=to_d) }}"
     class="quick-filter__btn {% if filter_from == from_d and filter_to == to_d %}quick-filter__btn--active{% endif %}">
    {{ label }}
  </a>
  {% endfor %}
</div>
```

---

## Step 3 — `static/css/profile.css`

Append:
```css
/* ── Quick-filter shortcut row ────────────────────────────────────── */

.quick-filter {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.quick-filter__btn {
    display: inline-block;
    padding: 0.35rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 0.8rem;
    color: var(--ink-muted);
    text-decoration: none;
    background: var(--paper-card);
    transition: border-color 0.15s, color 0.15s;
}

.quick-filter__btn:hover {
    border-color: var(--accent);
    color: var(--accent);
}

.quick-filter__btn--active {
    background: var(--accent-light);
    border-color: var(--accent);
    color: var(--accent);
    font-weight: 500;
}
```

---

## Verification
1. Profile page loads without error
2. Four shortcut links appear: All Time, This Month, Last 3 Months, Last 6 Months
3. Clicking "This Month" pre-fills from_date = first of current month, to_date = today and filters correctly
4. "All Time" clears the filter
5. Active shortcut is visually highlighted
6. Manual date-range filter still works unchanged
7. All 199 existing tests continue to pass
