import re
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for, abort, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import (
    get_db, init_db, seed_db, create_user, get_user_by_email,
    get_user_by_id, _fmt_date, _fmt_member_since,
    get_user_expenses, get_user_stats, get_user_categories,
    add_expense, get_expense_by_id, update_expense,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"

_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")

EXPENSE_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

with app.app_context():
    init_db()
    seed_db()


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name:
        return render_template("register.html", error="Name is required.")
    if not email:
        return render_template("register.html", error="Email is required.")
    if not password:
        return render_template("register.html", error="Password is required.")
    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    password_hash = generate_password_hash(password)

    try:
        user_id = create_user(name, email, password_hash)
    except Exception:
        abort(500)

    if user_id is None:
        return render_template("register.html", error="An account with that email already exists.")

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email:
        return render_template("login.html", error="Email is required.")
    if not password:
        return render_template("login.html", error="Password is required.")

    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("landing"))


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
    filter_to = request.args.get("to_date", "").strip()
    filter_error = None
    filter_hint = None
    active_filter = False

    if filter_from and not _DATE_RE.match(filter_from):
        filter_error = "Invalid start date. Use YYYY-MM-DD format."
        filter_from = filter_to = ""
    elif filter_to and not _DATE_RE.match(filter_to):
        filter_error = "Invalid end date. Use YYYY-MM-DD format."
        filter_from = filter_to = ""
    elif bool(filter_from) != bool(filter_to):
        filter_hint = "Please provide both a start and an end date."
        filter_from = filter_to = ""
    elif filter_from and filter_to:
        if filter_from > filter_to:
            filter_error = "Start date must be on or before the end date."
            filter_from = filter_to = ""
        else:
            active_filter = True

    user_id = session["user_id"]
    from_arg = filter_from if active_filter else None
    to_arg = filter_to if active_filter else None

    expenses = get_user_expenses(user_id, from_arg, to_arg)
    stats = get_user_stats(user_id, from_arg, to_arg)
    categories = get_user_categories(user_id, from_arg, to_arg)

    filter_from_display = _fmt_date(filter_from) if active_filter else ""
    filter_to_display = _fmt_date(filter_to) if active_filter else ""

    _today = date.today()
    quick_filters = {
        "This Month":    (_today.replace(day=1).isoformat(), _today.isoformat()),
        "Last 3 Months": ((_today - timedelta(days=90)).isoformat(), _today.isoformat()),
        "Last 6 Months": ((_today - timedelta(days=180)).isoformat(), _today.isoformat()),
    }

    return render_template(
        "profile.html",
        user=user, stats=stats, expenses=expenses, categories=categories,
        filter_from=filter_from, filter_to=filter_to,
        filter_from_display=filter_from_display, filter_to_display=filter_to_display,
        active_filter=active_filter,
        filter_error=filter_error, filter_hint=filter_hint,
        quick_filters=quick_filters,
    )


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
            "date": expense["date"],        # raw YYYY-MM-DD — NOT _fmt_date()
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


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
