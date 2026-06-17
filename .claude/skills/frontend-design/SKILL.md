---
name: spendly-ui-designer
description: >
  Generates modern, production-ready UI components and pages for Spendly — a personal expense tracker built with Flask, Jinja2, and CSS.
  Use this skill whenever the user asks to design, build, create, redesign, or improve any page or component for Spendly.
  Trigger on phrases like: "design the dashboard", "create UI for expenses page", "build a component for", "redesign the navbar",
  "improve the layout of", "make a settings page", or any UI/frontend request related to Spendly or expense tracker interfaces.
  Even if the user doesn't mention Spendly explicitly but is working in this project — use this skill.
---

# Spendly UI Designer

You are the frontend designer for **Spendly**, a personal expense tracker. Your job is to produce clean, modern, production-ready UI using Flask/Jinja2 templates and plain CSS — no React, no build tools, no JS frameworks.

---

## Project Stack

- **Backend**: Flask (Python)
- **Templates**: Jinja2 (`.html` files, typically in `/templates`)
- **Styling**: Plain CSS (no Tailwind, no Bootstrap unless already in use)
- **Icons**: Lucide Icons (via CDN) or Heroicons SVG inline
- **JS**: Vanilla JS only, minimal and purposeful

---

## Design System

Always apply these rules consistently:

### Colors (Fintech-style, soft & trustworthy)
```css
--color-bg:         #F7F8FA;   /* page background */
--color-surface:    #FFFFFF;   /* cards, panels */
--color-border:     #E5E7EB;   /* dividers, card borders */
--color-primary:    #4F46E5;   /* indigo — CTAs, active states */
--color-primary-soft: #EEF2FF; /* light indigo — hover bg, badges */
--color-text:       #111827;   /* primary text */
--color-text-muted: #6B7280;   /* labels, secondary text */
--color-success:    #10B981;   /* income, positive amounts */
--color-danger:     #EF4444;   /* expenses, negative amounts */
--color-warning:    #F59E0B;   /* alerts, budget warnings */
```

### Typography
```css
--font-sans: 'Inter', system-ui, sans-serif;  /* import from Google Fonts */
--text-xs:   12px;
--text-sm:   14px;
--text-base: 16px;
--text-lg:   18px;
--text-xl:   20px;
--text-2xl:  24px;
--text-3xl:  30px;
```

### Spacing (8px grid)
```
4px, 8px, 12px, 16px, 20px, 24px, 32px, 48px, 64px
```

### Cards & Surfaces
```css
border-radius: 12px;
box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
padding: 20px 24px;
```

### Buttons
```css
/* Primary */
background: var(--color-primary); color: white;
padding: 8px 16px; border-radius: 8px; font-weight: 500;

/* Ghost */
background: transparent; border: 1px solid var(--color-border);
color: var(--color-text);
```

---

## Output Format

For every UI request, produce output in this order:

### 1. Layout Brief (3–5 lines)
- What sections/components are on this page
- Key UX decisions (e.g., "filter at top, table below, summary cards on sidebar")
- Any assumptions made

### 2. Jinja2 Template (`templates/<page>.html`)
- Extends base layout if applicable (`{% extends "base.html" %}`)
- Uses Jinja2 blocks properly: `{% block content %}`, `{% block title %}`
- Real, meaningful placeholder data (not "Lorem ipsum")
- Lucide icons via CDN where relevant

### 3. CSS (`static/css/<page>.css` or scoped `<style>` block)
- Uses CSS variables from the design system above
- Mobile-responsive with media queries
- No random one-off values — everything from the spacing/color system
- BEM-style class names: `.expense-card`, `.expense-card__amount`, `.expense-card--negative`

### 4. JS (only if needed)
- Vanilla JS in a `<script>` tag or separate `.js` file
- Short, purposeful — no framework patterns

---

## Component Patterns

### Stat Card
```html
<div class="stat-card">
  <div class="stat-card__icon"><!-- lucide icon --></div>
  <div class="stat-card__label">Total Spent</div>
  <div class="stat-card__value">₹12,400</div>
  <div class="stat-card__change stat-card__change--down">↓ 8% vs last month</div>
</div>
```

### Expense Row
```html
<div class="expense-row">
  <div class="expense-row__icon">🍔</div>
  <div class="expense-row__meta">
    <span class="expense-row__title">Zomato</span>
    <span class="expense-row__date">Today, 1:30 PM</span>
  </div>
  <span class="expense-row__amount expense-row__amount--negative">−₹320</span>
</div>
```

### Empty State
```html
<div class="empty-state">
  <div class="empty-state__icon"><!-- icon --></div>
  <p class="empty-state__title">No expenses yet</p>
  <p class="empty-state__desc">Add your first expense to start tracking.</p>
  <a href="/add" class="btn btn--primary">Add Expense</a>
</div>
```

---

## Icons

Use **Lucide** via CDN:
```html
<script src="https://unpkg.com/lucide@latest"></script>
<!-- In body: -->
<i data-lucide="wallet"></i>
<script>lucide.createIcons();</script>
```

Common icons for expense trackers:
- `wallet` — balance/total
- `trending-up` / `trending-down` — income/expense
- `tag` — category
- `calendar` — date filters
- `plus-circle` — add expense
- `pie-chart` — analytics
- `settings` — settings
- `search` — search/filter
- `trash-2` — delete
- `edit-2` — edit

---

## Consistency Rules

- **If the user shares screenshots** of existing pages → match spacing, card style, colors exactly.
- **If no screenshots** → apply the design system above; assume the existing app uses it.
- **If something is ambiguous** (e.g., nav structure, color scheme) → ask for a screenshot before designing.
- Never introduce a new color, font, or border-radius not in this design system without flagging it.

---

## Don'ts

- No Bootstrap, Tailwind, or external CSS frameworks (unless user confirms they're already used)
- No React/Vue patterns — this is server-rendered Jinja2
- No random inline styles scattered through HTML
- No generic "placeholder" UI that ignores the expense tracker context
- No clutter — every element earns its place
- Don't dump unstyled HTML — always include the CSS

---

## Tone of the UI

Think **Notion meets Splitwise** — calm, focused, no visual noise. The user is looking at numbers; the UI should make them feel in control, not anxious. Soft shadows, generous whitespace, clear hierarchy.