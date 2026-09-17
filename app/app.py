import sys
import os
import json
import math
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db, init_db, get_meta, DB_PATH

from flask import Flask, render_template, request, redirect, url_for, flash, session

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, "templates"),
    static_folder=os.path.join(PROJECT_ROOT, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "aster-test-build-dev-secret")

# Site-wide password protection. The actual username and password are set as
# environment variables on Render, never committed here.
SITE_USERNAME = os.environ.get("SITE_USERNAME")
SITE_PASSWORD = os.environ.get("SITE_PASSWORD")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == SITE_USERNAME and password == SITE_PASSWORD:
            session["authed"] = True
            session.permanent = bool(request.form.get("remember"))
            return redirect(request.args.get("next") or url_for("overview"))
        error = "Incorrect username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def require_login():
    if not SITE_USERNAME or not SITE_PASSWORD:
        # Auth not configured (e.g. running locally without the env vars set)
        return
    if request.endpoint in ("login", "static"):
        return
    if not session.get("authed"):
        return redirect(url_for("login", next=request.path))

CATEGORIES = [
    "Artic HGV", "Rigid HGV", "7.5T Rigid", "Transit Van", "Sprinter Van", "Pickup",
]

# ---------------------------------------------------------------------------
# Illustrative driver-level data for the Explorer / Roadmap concept pages.
#
# The real database (see db.py) tracks vehicles and claims at depot level —
# there is no telematics feed and no drivers table, so nothing below is real
# data. It mirrors the "vision" content from the original concept preview:
# clearly labelled sample profiles showing what Aster would surface once a
# telematics provider is connected, not a claim about any real individual.
# ---------------------------------------------------------------------------
SAMPLE_DRIVERS = {
    "Birmingham": [
        {
            "slug": "r-hutton", "name": "R. Hutton", "role": "HGV Class 1 Driver",
            "service": "6 yrs 1 mth", "licence": "Cat C+E", "points": 3, "tier": "med",
            "metrics": {"Harsh braking": 58, "Harsh cornering": 34, "Speeding events": 41, "Night driving": 22},
            "blurb": "Above-depot-average harsh braking events over the last quarter, concentrated on the A38 corridor. No claims recorded in the last 12 months.",
            "actions": ["Book a one-to-one coaching session on braking technique", "Review telematics trend again at next monthly check-in"],
        },
        {
            "slug": "k-adeyemi", "name": "K. Adeyemi", "role": "7.5T Driver",
            "service": "1 yr 8 mths", "licence": "Cat C", "points": 0, "tier": "low",
            "metrics": {"Harsh braking": 19, "Harsh cornering": 14, "Speeding events": 9, "Night driving": 31},
            "blurb": "Consistently smooth driving profile since joining. A good candidate for the depot's driver mentor scheme.",
            "actions": ["No action required — maintain current monitoring"],
        },
    ],
    "Bristol": [
        {
            "slug": "d-price", "name": "D. Price", "role": "Artic Driver",
            "service": "9 yrs 4 mths", "licence": "Cat C+E", "points": 6, "tier": "high",
            "metrics": {"Harsh braking": 71, "Harsh cornering": 63, "Speeding events": 68, "Night driving": 44},
            "blurb": "Elevated risk score across all telematics measures this quarter, alongside two own-damage claims in the last 12 months. Flagged for review.",
            "actions": ["Schedule a formal driving-standards review", "Check licence endorsements are still within policy terms"],
        },
        {
            "slug": "s-malik", "name": "S. Malik", "role": "Transit Van Driver",
            "service": "3 yrs", "licence": "Cat B", "points": 0, "tier": "low",
            "metrics": {"Harsh braking": 23, "Harsh cornering": 17, "Speeding events": 12, "Night driving": 8},
            "blurb": "No adverse telematics events recorded. Depot's lowest-mileage-per-incident driver.",
            "actions": ["No action required"],
        },
    ],
    "Glasgow": [
        {
            "slug": "a-mackenzie", "name": "A. MacKenzie", "role": "Rigid HGV Driver",
            "service": "5 yrs 6 mths", "licence": "Cat C", "points": 3, "tier": "med",
            "metrics": {"Harsh braking": 46, "Harsh cornering": 39, "Speeding events": 52, "Night driving": 27},
            "blurb": "Speeding-event frequency has risen over the last two months, mainly on dual-carriageway sections.",
            "actions": ["Share route-specific speed reminder ahead of winter conditions"],
        },
        {
            "slug": "l-fraser", "name": "L. Fraser", "role": "Sprinter Van Driver",
            "service": "2 yrs 2 mths", "licence": "Cat B", "points": 0, "tier": "low",
            "metrics": {"Harsh braking": 15, "Harsh cornering": 11, "Speeding events": 6, "Night driving": 19},
            "blurb": "Steady, low-risk profile since joining. No claims on record.",
            "actions": ["No action required"],
        },
    ],
    "Leeds": [
        {
            "slug": "j-oconnor", "name": "J. O'Connor", "role": "Artic Driver",
            "service": "7 yrs", "licence": "Cat C+E", "points": 3, "tier": "med",
            "metrics": {"Harsh braking": 49, "Harsh cornering": 44, "Speeding events": 38, "Night driving": 51},
            "blurb": "Regularly runs night trunking routes; night-driving events tracking slightly above depot average.",
            "actions": ["Confirm fatigue-management rest breaks are being logged correctly"],
        },
        {
            "slug": "m-wilkinson", "name": "M. Wilkinson", "role": "Pickup Driver",
            "service": "11 mths", "licence": "Cat B", "points": 0, "tier": "low",
            "metrics": {"Harsh braking": 21, "Harsh cornering": 18, "Speeding events": 14, "Night driving": 5},
            "blurb": "New starter with a clean telematics record so far.",
            "actions": ["Complete standard 12-month new-starter review"],
        },
    ],
    "Manchester": [
        {
            "slug": "t-nwosu", "name": "T. Nwosu", "role": "Rigid HGV Driver",
            "service": "4 yrs 7 mths", "licence": "Cat C", "points": 6, "tier": "high",
            "metrics": {"Harsh braking": 66, "Harsh cornering": 58, "Speeding events": 61, "Night driving": 33},
            "blurb": "Two at-fault claims in the last 12 months alongside a high harsh-cornering rate. Highest combined risk score at the depot.",
            "actions": ["Schedule a formal driving-standards review", "Consider a defensive-driving refresher course"],
        },
        {
            "slug": "e-brennan", "name": "E. Brennan", "role": "7.5T Driver",
            "service": "3 yrs 3 mths", "licence": "Cat C", "points": 0, "tier": "low",
            "metrics": {"Harsh braking": 17, "Harsh cornering": 13, "Speeding events": 10, "Night driving": 12},
            "blurb": "Consistently strong telematics profile across all measures.",
            "actions": ["No action required"],
        },
    ],
    "Newcastle": [
        {
            "slug": "p-dodds", "name": "P. Dodds", "role": "Transit Van Driver",
            "service": "2 yrs 9 mths", "licence": "Cat B", "points": 3, "tier": "med",
            "metrics": {"Harsh braking": 44, "Harsh cornering": 37, "Speeding events": 47, "Night driving": 16},
            "blurb": "Speeding events above depot average, concentrated on the A1 corridor south of the depot.",
            "actions": ["Share route-specific speed reminder"],
        },
        {
            "slug": "c-armstrong", "name": "C. Armstrong", "role": "Sprinter Van Driver",
            "service": "5 yrs 1 mth", "licence": "Cat B", "points": 0, "tier": "low",
            "metrics": {"Harsh braking": 20, "Harsh cornering": 16, "Speeding events": 11, "Night driving": 9},
            "blurb": "Low-risk profile maintained consistently since joining.",
            "actions": ["No action required"],
        },
    ],
}


def as_of_today(conn):
    meta_as_of = get_meta(conn, "as_of")
    if meta_as_of:
        try:
            return datetime.strptime(meta_as_of, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def renewal_days(conn):
    row = conn.execute(
        "SELECT period_end FROM covers WHERE is_primary=1 LIMIT 1"
    ).fetchone()
    if not row or not row["period_end"]:
        return None
    end = datetime.strptime(row["period_end"], "%Y-%m-%d").date()
    return (end - as_of_today(conn)).days


@app.context_processor
def inject_globals():
    conn = get_db()
    days = renewal_days(conn)
    conn.close()
    return dict(renewal_days=days)


@app.route("/")
def index():
    return redirect(url_for("overview"))


@app.route("/overview")
def overview():
    conn = get_db()
    kpi = get_meta(conn, "kpi", {}) or {}
    vehicle_count = conn.execute(
        "SELECT COUNT(*) c FROM vehicles WHERE status='On cover'"
    ).fetchone()["c"]
    total_claims = conn.execute("SELECT COUNT(*) c FROM claims").fetchone()["c"]
    total_incurred = conn.execute(
        "SELECT COALESCE(SUM(incurred),0) s FROM claims"
    ).fetchone()["s"]
    open_claims = conn.execute(
        "SELECT COUNT(*) c FROM claims WHERE closed=0"
    ).fetchone()["c"]
    loss_ratio = get_meta(conn, "loss_ratio", {}) or {}
    conn.close()
    return render_template(
        "overview.html",
        active_tab="overview",
        vehicle_count=vehicle_count,
        total_claims=total_claims,
        total_incurred=total_incurred,
        open_claims=open_claims,
        loss_ratio_pct=loss_ratio.get("overall_loss_ratio", kpi.get("loss_ratio")),
        loss_ratio_target=loss_ratio.get("target", 65.0),
    )


@app.route("/portfolio")
def portfolio():
    conn = get_db()
    covers = conn.execute("SELECT * FROM covers ORDER BY is_primary DESC").fetchall()

    q = request.args.get("q", "").strip()
    depot = request.args.get("depot", "")
    category = request.args.get("category", "")
    sort_key = request.args.get("sort", "reg")
    sort_dir = request.args.get("dir", "asc")

    sql = "SELECT * FROM vehicles WHERE 1=1"
    params = []
    if q:
        sql += " AND (reg LIKE ? OR model LIKE ? OR make LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if depot:
        sql += " AND depot=?"
        params.append(depot)
    if category:
        sql += " AND category=?"
        params.append(category)

    valid_sorts = {"reg", "cover_start", "category", "depot", "status"}
    if sort_key not in valid_sorts:
        sort_key = "reg"
    sql += f" ORDER BY {sort_key} {'DESC' if sort_dir == 'desc' else 'ASC'}"

    vehicles = conn.execute(sql, params).fetchall()

    depots = [r["depot"] for r in conn.execute(
        "SELECT DISTINCT depot FROM vehicles ORDER BY depot"
    ).fetchall()]
    on_cover = conn.execute(
        "SELECT COUNT(*) c FROM vehicles WHERE status='On cover'"
    ).fetchone()["c"]
    cutoff = (as_of_today(conn) - timedelta(days=365)).isoformat()
    added_12m = conn.execute(
        "SELECT COUNT(*) c FROM vehicles WHERE status='On cover' AND cover_start >= ?",
        (cutoff,),
    ).fetchone()["c"]
    removed_12m = conn.execute(
        "SELECT COUNT(*) c FROM vehicles WHERE status='Removed' AND cover_end >= ?",
        (cutoff,),
    ).fetchone()["c"]

    conn.close()
    return render_template(
        "portfolio.html",
        active_tab="portfolio",
        covers=covers,
        vehicles=vehicles,
        depots=depots,
        categories=CATEGORIES,
        q=q, depot=depot, category=category, sort_key=sort_key, sort_dir=sort_dir,
        on_cover=on_cover, added_12m=added_12m, removed_12m=removed_12m,
    )


@app.route("/portfolio/vehicles/new", methods=["GET", "POST"])
def new_vehicle():
    conn = get_db()
    depots = [r["depot"] for r in conn.execute(
        "SELECT DISTINCT depot FROM vehicles ORDER BY depot"
    ).fetchall()]

    if request.method == "POST":
        reg = request.form.get("reg", "").strip().upper()
        depot = request.form.get("depot", "")
        category = request.form.get("category", "")
        make = request.form.get("make", "").strip()
        model = request.form.get("model", "").strip()
        value = request.form.get("value") or None
        year = request.form.get("year") or None
        gvw = request.form.get("gvw") or None
        cover_start = request.form.get("cover_start")
        cover_end = request.form.get("cover_end") or None
        status = request.form.get("status", "On cover")
        notes = request.form.get("notes", "").strip()

        errors = []
        if not depot: errors.append("Depot is required.")
        if not category: errors.append("Category is required.")
        if not make: errors.append("Make is required.")
        if not model: errors.append("Model is required.")
        if not cover_start: errors.append("Date on is required.")

        if not reg:
            prefix = depot[:2].upper() if depot else "XX"
            existing = conn.execute("SELECT COUNT(*) c FROM vehicles").fetchone()["c"]
            reg = f"{prefix}{datetime.now().year % 100}GEN{existing+1:03d}"

        if not errors:
            existing = conn.execute("SELECT id FROM vehicles WHERE reg=?", (reg,)).fetchone()
            if existing:
                errors.append(f"Registration {reg} already exists on the schedule.")

        if errors:
            conn.close()
            return render_template(
                "vehicle_form.html", active_tab="portfolio", depots=depots,
                categories=CATEGORIES, errors=errors, form=request.form,
            )

        conn.execute(
            """INSERT INTO vehicles (reg, depot, category, make, model, value, year, gvw,
               cover_start, cover_end, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (reg, depot, category, make, model, value, year, gvw,
             cover_start, cover_end, status, notes),
        )
        conn.commit()
        conn.close()
        flash(f"{reg} added to the Fleet Motor schedule from {cover_start}.")
        return redirect(url_for("portfolio"))

    conn.close()
    today = as_of_today(get_db()).isoformat()
    return render_template(
        "vehicle_form.html", active_tab="portfolio", depots=depots,
        categories=CATEGORIES, errors=[], form={"cover_start": today, "status": "On cover"},
    )


@app.route("/portfolio/vehicles/<int:vehicle_id>/remove", methods=["POST"])
def remove_vehicle(vehicle_id):
    conn = get_db()
    v = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
    if v:
        eff_date = request.form.get("cover_end") or as_of_today(conn).isoformat()
        conn.execute(
            "UPDATE vehicles SET status='Removed', cover_end=? WHERE id=?",
            (eff_date, vehicle_id),
        )
        conn.commit()
        flash(f"{v['reg']} removed from cover from {eff_date}.")
    conn.close()
    return redirect(url_for("portfolio"))


@app.route("/claims")
def claims():
    conn = get_db()
    q = request.args.get("q", "").strip()
    depot = request.args.get("depot", "")
    period = request.args.get("period", "all")
    basis = request.args.get("basis", "ground_up")
    sort_key = request.args.get("sort", "loss_date")
    sort_dir = request.args.get("dir", "desc")

    as_of = as_of_today(conn)
    sql = "SELECT * FROM claims WHERE 1=1"
    params = []
    if q:
        sql += " AND (ref LIKE ? OR depot LIKE ? OR cause LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if depot:
        sql += " AND depot=?"
        params.append(depot)

    loss_ratio_meta = get_meta(conn, "loss_ratio", {}) or {}
    labels = loss_ratio_meta.get("labels", [])
    current_py = labels[-1] if labels else None
    prior_py = labels[-2] if len(labels) > 1 else None

    if period == "policy_year" and current_py:
        sql += " AND policy_year=?"
        params.append(current_py)
    elif period == "prior_policy_year" and prior_py:
        sql += " AND policy_year=?"
        params.append(prior_py)
    elif period == "12m":
        cutoff = (as_of - timedelta(days=365)).isoformat()
        sql += " AND loss_date >= ?"
        params.append(cutoff)
    elif period == "ytd":
        cutoff = date(as_of.year, 1, 1).isoformat()
        sql += " AND loss_date >= ?"
        params.append(cutoff)

    valid_sorts = {"ref", "depot", "loss_date", "cause", "status", "incurred"}
    if sort_key not in valid_sorts:
        sort_key = "loss_date"
    sql += f" ORDER BY {sort_key} {'DESC' if sort_dir == 'desc' else 'ASC'}"

    rows = conn.execute(sql, params).fetchall()

    total_claims = len(rows)
    total_incurred = sum(r["incurred"] for r in rows)
    open_claims = sum(1 for r in rows if not r["closed"])
    closed_claims = total_claims - open_claims
    avg_cost = (total_incurred / total_claims) if total_claims else 0
    on_cover = conn.execute(
        "SELECT COUNT(*) c FROM vehicles WHERE status='On cover'"
    ).fetchone()["c"] or 1
    ccpv = total_incurred / on_cover

    overall_lr = loss_ratio_meta.get("overall_loss_ratio")
    target = loss_ratio_meta.get("target", 65.0)
    cur_lr = None
    prior_lr = None
    if labels:
        lr_list = loss_ratio_meta.get("loss_ratio", [])
        if lr_list:
            cur_lr = lr_list[-1]
            prior_lr = lr_list[-2] if len(lr_list) > 1 else None

    depots = [r["depot"] for r in conn.execute(
        "SELECT DISTINCT depot FROM claims ORDER BY depot"
    ).fetchall()]

    # Register pagination — stats above are computed from the full filtered
    # set (`rows`); only the table itself is sliced to one page.
    PER_PAGE = 25
    page = request.args.get("page", 1, type=int) or 1
    total_matching = len(rows)
    total_pages = max(1, math.ceil(total_matching / PER_PAGE))
    page = max(1, min(page, total_pages))
    page_rows = rows[(page - 1) * PER_PAGE: page * PER_PAGE]
    showing_from = (page - 1) * PER_PAGE + 1 if total_matching else 0
    showing_to = min(page * PER_PAGE, total_matching)

    # --- Chart sections below mirror the concept dashboard's analysis
    # panels. They're computed from the whole claims register regardless of
    # the register's own filters above, matching Fleet Performance's charts.
    depot_stats_all = conn.execute(
        """SELECT depot, COUNT(*) claims, SUM(incurred) incurred, AVG(incurred) avg_cost
           FROM claims GROUP BY depot ORDER BY claims DESC"""
    ).fetchall()
    depot_count_chart = build_bar_chart(
        [r["depot"] for r in depot_stats_all], [r["claims"] for r in depot_stats_all]
    )
    depot_incurred_chart = build_bar_chart(
        [r["depot"] for r in depot_stats_all], [r["incurred"] or 0 for r in depot_stats_all]
    )
    depot_avg_chart = build_bar_chart(
        [r["depot"] for r in depot_stats_all], [round(r["avg_cost"] or 0) for r in depot_stats_all]
    )

    cause_rows = conn.execute(
        "SELECT cause, COUNT(*) c, SUM(incurred) s FROM claims GROUP BY cause ORDER BY c DESC"
    ).fetchall()
    top_cause = cause_rows[:5]
    rest_cause = cause_rows[5:]
    cause_vol_labels = [r["cause"] for r in top_cause]
    cause_vol_values = [r["c"] for r in top_cause]
    if rest_cause:
        cause_vol_labels.append("Other")
        cause_vol_values.append(sum(r["c"] for r in rest_cause))
    cause_donut = build_donut_chart(cause_vol_labels, cause_vol_values)

    # These charts render two-up in a grid cell (see claims.html's
    # chart-grid-row), so they're built at a narrower intrinsic width than
    # the single-chart 600px default — sized to fill their column without
    # needing horizontal scroll at typical desktop widths.
    cause_cost_sorted = sorted(cause_rows, key=lambda r: r["s"] or 0, reverse=True)[:6]
    cause_cost_chart = build_hbar_chart(
        [r["cause"] for r in cause_cost_sorted], [r["s"] or 0 for r in cause_cost_sorted], width=420
    )

    trend_labels, trend_counts, trend_costs = build_monthly_trend(conn)
    trend_volume_chart = build_line_chart(trend_labels, trend_counts, width=420)
    trend_cost_chart = build_line_chart(trend_labels, trend_costs, width=420)

    status_rows = conn.execute("SELECT status, COUNT(*) c FROM claims GROUP BY status").fetchall()
    status_groups = {"Open": 0, "Closed": 0, "Litigated": 0}
    for r in status_rows:
        key = "Open" if r["status"].startswith("Open") else ("Closed" if r["status"].startswith("Closed") else "Litigated")
        status_groups[key] += r["c"]
    status_donut = build_donut_chart(list(status_groups.keys()), list(status_groups.values()))

    fault_rows = conn.execute(
        "SELECT fault, COUNT(*) c FROM claims WHERE fault IS NOT NULL GROUP BY fault ORDER BY c DESC"
    ).fetchall()
    fault_donut = build_donut_chart([r["fault"] for r in fault_rows], [r["c"] for r in fault_rows])

    days_labels, days_counts = build_days_to_close(conn)
    days_to_close_chart = build_bar_chart(days_labels, days_counts, width=420)

    top10_rows = conn.execute(
        "SELECT ref, depot, incurred FROM claims ORDER BY incurred DESC LIMIT 10"
    ).fetchall()
    top10_chart = build_hbar_chart(
        [f"{r['ref']} · {r['depot']}" for r in top10_rows], [r["incurred"] or 0 for r in top10_rows],
        width=420, row_h=38,
    )

    weekly_labels, weekly_series = build_weekly_open_by_depot(conn)
    weekly_chart = build_multiline_chart(weekly_labels, weekly_series)

    conn.close()
    return render_template(
        "claims.html",
        active_tab="claims",
        rows=page_rows, q=q, depot=depot, depots=depots, period=period, basis=basis,
        sort_key=sort_key, sort_dir=sort_dir,
        total_claims=total_claims, total_incurred=total_incurred,
        open_claims=open_claims, closed_claims=closed_claims, avg_cost=avg_cost,
        ccpv=ccpv, overall_lr=overall_lr, target=target, cur_lr=cur_lr, prior_lr=prior_lr,
        current_py=current_py, prior_py=prior_py,
        page=page, total_pages=total_pages, total_matching=total_matching,
        showing_from=showing_from, showing_to=showing_to,
        depot_count_chart=depot_count_chart, depot_incurred_chart=depot_incurred_chart,
        depot_avg_chart=depot_avg_chart,
        cause_donut=cause_donut, cause_cost_chart=cause_cost_chart,
        trend_volume_chart=trend_volume_chart, trend_cost_chart=trend_cost_chart,
        status_donut=status_donut, fault_donut=fault_donut,
        days_to_close_chart=days_to_close_chart, top10_chart=top10_chart,
        weekly_chart=weekly_chart,
    )


@app.route("/claims/new", methods=["GET", "POST"])
def new_claim():
    conn = get_db()
    depots = [r["depot"] for r in conn.execute(
        "SELECT DISTINCT depot FROM vehicles ORDER BY depot"
    ).fetchall()]
    causes = [r[0] for r in conn.execute(
        "SELECT DISTINCT cause FROM claims ORDER BY cause"
    ).fetchall()]

    if request.method == "POST":
        depot = request.form.get("depot", "")
        vehicle_type = request.form.get("vehicle_type", "").strip()
        loss_date = request.form.get("loss_date")
        cause = request.form.get("cause", "").strip()
        fault = request.form.get("fault", "")
        own_damage = request.form.get("own_damage", "")
        reserve = request.form.get("reserve") or 0
        notes = request.form.get("notes", "").strip()

        errors = []
        if not depot: errors.append("Depot is required.")
        if not vehicle_type: errors.append("Vehicle is required.")
        if not loss_date: errors.append("Date of loss is required.")
        if not cause: errors.append("Cause is required.")
        if not fault: errors.append("Liability is required.")
        if not own_damage: errors.append("Own damage is required.")

        if errors:
            conn.close()
            return render_template(
                "claim_form.html", active_tab="claims", depots=depots, causes=causes,
                errors=errors, form=request.form,
            )

        loss_ratio_meta = get_meta(conn, "loss_ratio", {}) or {}
        labels = loss_ratio_meta.get("labels", [])
        d = datetime.strptime(loss_date, "%Y-%m-%d").date()
        start_year = d.year if (d.month > 10 or (d.month == 10 and d.day >= 11)) else d.year - 1
        policy_year = f"{start_year}-{str((start_year + 1) % 100).zfill(2)}"

        prefix_map = {}
        for r in conn.execute("SELECT ref, depot FROM claims").fetchall():
            m = r["ref"].split("-")
            if len(m) >= 2:
                prefix_map.setdefault(r["depot"], []).append(r["ref"])
        depot_code = depot[:3].upper()
        existing_refs = [r["ref"] for r in conn.execute(
            "SELECT ref FROM claims WHERE depot=?", (depot,)
        ).fetchall()]
        nums = []
        for ref in existing_refs:
            try:
                nums.append(int(ref.split("-")[-1]))
            except ValueError:
                pass
        next_num = (max(nums) + 1) if nums else 10001
        ref = f"BW-{depot_code}-{next_num}"

        reserve_val = float(reserve) if reserve else 0.0
        conn.execute(
            """INSERT INTO claims (ref, depot, vehicle_type, loss_date, cause, status, fault,
               own_damage, paid, reserve, incurred, days_open, policy_year, closed, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ref, depot, vehicle_type, loss_date, cause, "Open - Under Investigation",
             fault, own_damage, 0, reserve_val, reserve_val, 0, policy_year, 0, notes),
        )
        conn.commit()
        conn.close()
        flash(f"Claim {ref} logged and added to the register.")
        return redirect(url_for("claims"))

    conn.close()
    today = date.today().isoformat()
    return render_template(
        "claim_form.html", active_tab="claims", depots=depots, causes=causes,
        errors=[], form={"loss_date": today},
    )


def build_line_chart(labels, values, target=None, width=600, height=220, pad=36):
    """Geometry for a simple SVG line chart, computed server-side so the
    template only has to draw pre-positioned points — no JS charting
    library required."""
    n = len(values)
    if n == 0:
        return None
    numeric = [v for v in values if v is not None]
    vmax = max(numeric + ([target] if target is not None else [0]) + [0])
    vmax = vmax * 1.15 if vmax else 1

    def x_at(i):
        if n == 1:
            return pad + (width - 2 * pad) / 2
        return pad + i * (width - 2 * pad) / (n - 1)

    def y_at(v):
        return height - pad - (v / vmax) * (height - 2 * pad)

    points = [
        {"x": round(x_at(i), 1), "y": round(y_at(v), 1), "label": lbl, "value": v}
        for i, (lbl, v) in enumerate(zip(labels, values)) if v is not None
    ]
    steps = 4
    grid = [
        {"y": round(height - pad - s / steps * (height - 2 * pad), 1), "value": round(vmax * s / steps, 1)}
        for s in range(steps + 1)
    ]
    return {
        "width": width, "height": height,
        "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        "points": points,
        "target_y": round(y_at(target), 1) if target is not None else None,
        "grid": grid,
    }


def build_bar_chart(labels, values, width=600, height=220, pad_left=44, pad_right=12, pad_top=12, pad_bottom=28):
    """Geometry for a simple vertical SVG bar chart."""
    n = len(values)
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    vmax = max(values) if values else 0
    vmax = vmax * 1.15 if vmax else 1
    gap = plot_w / n if n else 0
    bar_w = gap * 0.55
    bars = []
    for i, (lbl, v) in enumerate(zip(labels, values)):
        bar_h = (v / vmax) * plot_h if vmax else 0
        x = pad_left + i * gap + (gap - bar_w) / 2
        y = pad_top + plot_h - bar_h
        bars.append({
            "x": round(x, 1), "y": round(y, 1), "w": round(bar_w, 1), "h": round(bar_h, 1),
            "label": lbl, "value": v, "label_x": round(x + bar_w / 2, 1),
        })
    steps = 4
    grid = [
        {"y": round(pad_top + plot_h - s / steps * plot_h, 1), "value": round(vmax * s / steps)}
        for s in range(steps + 1)
    ]
    return {
        "width": width, "height": height, "bars": bars, "grid": grid,
        "axis_x1": pad_left, "axis_x2": width - pad_right, "base_y": pad_top + plot_h,
    }


def build_hbar_chart(labels, values, width=600, row_h=46, pad_x=4, pad_top=8, pad_bottom=8):
    """Geometry for a horizontal bar-per-row chart, with the label sitting
    above its own bar rather than in a side column — the cause-of-loss
    labels are long enough that a fixed label column would either clip
    them or force the bars into an unreasonably narrow strip."""
    n = len(values)
    height = pad_top + pad_bottom + n * row_h
    plot_w = width - 2 * pad_x
    vmax = max(values) if values else 0
    vmax = vmax * 1.15 if vmax else 1
    bars = []
    for i, (lbl, v) in enumerate(zip(labels, values)):
        row_top = pad_top + i * row_h
        bar_w = (v / vmax) * plot_w if vmax else 0
        bars.append({
            "label": lbl, "value": v,
            "label_x": pad_x, "label_y": round(row_top + 12, 1),
            "x": pad_x, "y": round(row_top + 20, 1), "w": round(bar_w, 1), "h": 16,
            "value_x": round(pad_x + bar_w + 8, 1), "value_y": round(row_top + 32, 1),
        })
    return {"width": width, "height": height, "bars": bars}


def build_donut_chart(labels, values, size=170, thickness=28):
    """Geometry for a simple SVG donut chart — one arc path per category,
    computed as plain polar-to-cartesian coordinates so no charting library
    is needed. Segments are coloured by position via the shared chart-cat-N
    CSS classes (see app.css), which also drive the multi-line chart and
    keep every chart's palette consistent."""
    total = sum(values) or 1
    cx = cy = size / 2
    r = size / 2 - 3
    r_inner = r - thickness
    start_angle = -90.0

    def polar(radius, deg):
        rad = math.radians(deg)
        return (cx + radius * math.cos(rad), cy + radius * math.sin(rad))

    segments = []
    for i, (lbl, v) in enumerate(zip(labels, values)):
        frac = v / total
        angle = min(frac * 360, 359.99)  # avoid a degenerate 360° arc
        end_angle = start_angle + angle
        large_arc = 1 if angle > 180 else 0
        x1, y1 = polar(r, start_angle)
        x2, y2 = polar(r, end_angle)
        x3, y3 = polar(r_inner, end_angle)
        x4, y4 = polar(r_inner, start_angle)
        path = (
            f"M {x1:.2f},{y1:.2f} "
            f"A {r:.2f},{r:.2f} 0 {large_arc} 1 {x2:.2f},{y2:.2f} "
            f"L {x3:.2f},{y3:.2f} "
            f"A {r_inner:.2f},{r_inner:.2f} 0 {large_arc} 0 {x4:.2f},{y4:.2f} Z"
        )
        segments.append({
            "label": lbl, "value": v, "pct": round(v / total * 100, 1),
            "path": path, "cat": i % 6,
        })
        start_angle += frac * 360
    return {"size": size, "segments": segments, "total": total}


def build_multiline_chart(labels, series, width=700, height=260, pad=40):
    """Geometry for a multi-series SVG line chart (one line per depot for
    the weekly risk trend) sharing one x-axis and y-scale. Each series gets
    a chart-cat-N colour class so it works with the same legend/toggle
    pattern as the donut charts."""
    n = len(labels)
    all_values = [v for s in series for v in s["values"]]
    vmax = max(all_values) if all_values else 0
    vmax = vmax * 1.15 if vmax else 1

    def x_at(i):
        if n <= 1:
            return pad + (width - 2 * pad) / 2
        return pad + i * (width - 2 * pad) / (n - 1)

    def y_at(v):
        return height - pad - (v / vmax) * (height - 2 * pad)

    out_series = []
    for idx, s in enumerate(series):
        points = [{"x": round(x_at(i), 1), "y": round(y_at(v), 1)} for i, v in enumerate(s["values"])]
        out_series.append({
            "name": s["name"], "cat": idx % 6,
            "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        })
    steps = 4
    grid = [
        {"y": round(height - pad - st / steps * (height - 2 * pad), 1), "value": round(vmax * st / steps)}
        for st in range(steps + 1)
    ]
    # Showing every label at typical widths (14+ weeks) is too cramped, so
    # thin them out — always keep the first and last so the range is clear.
    show_every = 2 if n > 8 else 1
    x_labels = [
        {"x": round(x_at(i), 1), "label": lbl}
        for i, lbl in enumerate(labels)
        if i % show_every == 0 or i == n - 1
    ]
    return {
        "width": width, "height": height, "series": out_series, "grid": grid,
        "x_labels": x_labels, "axis_x1": pad, "axis_x2": width - pad,
    }


def build_weekly_open_by_depot(conn, num_weeks=14):
    """Open-claims-per-week, per depot, for the last `num_weeks` weeks —
    a snapshot metric computed from loss_date/close_date rather than stored
    history, since the register doesn't track status changes over time."""
    as_of = as_of_today(conn)
    week_ends = [as_of - timedelta(weeks=i) for i in range(num_weeks - 1, -1, -1)]
    week_iso = [w.isoformat() for w in week_ends]

    all_rows = conn.execute("SELECT depot, loss_date, closed, close_date FROM claims").fetchall()
    by_depot = {}
    for r in all_rows:
        by_depot.setdefault(r["depot"], []).append(r)

    series = []
    for depot in sorted(by_depot.keys()):
        depot_rows = by_depot[depot]
        values = []
        for w_iso in week_iso:
            count = sum(
                1 for r in depot_rows
                if r["loss_date"] <= w_iso
                and (not r["closed"] or not r["close_date"] or r["close_date"] > w_iso)
            )
            values.append(count)
        series.append({"name": depot, "values": values})

    labels = [w.strftime("%d %b") for w in week_ends]
    return labels, series


def build_monthly_trend(conn, months=12):
    """Claim volume and incurred cost per calendar month, for the trailing
    `months` months ending at as_of_today."""
    rows = conn.execute(
        "SELECT strftime('%Y-%m', loss_date) ym, COUNT(*) c, SUM(incurred) s FROM claims GROUP BY ym"
    ).fetchall()
    by_ym = {r["ym"]: r for r in rows}

    as_of = as_of_today(conn)
    keys = []
    y, m = as_of.year, as_of.month
    for i in range(months - 1, -1, -1):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        keys.append(f"{yy:04d}-{mm:02d}")

    labels, counts, costs = [], [], []
    for k in keys:
        r = by_ym.get(k)
        labels.append(datetime.strptime(k, "%Y-%m").strftime("%b %y"))
        counts.append(r["c"] if r else 0)
        costs.append((r["s"] or 0) if r else 0)
    return labels, counts, costs


def build_days_to_close(conn):
    """Distribution of days-from-loss-to-close for closed claims, bucketed
    into fixed ranges for a simple bar chart."""
    rows = conn.execute("SELECT days_open FROM claims WHERE closed=1").fetchall()
    buckets = [("0-14", 0, 14), ("15-30", 15, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, 10**6)]
    counts = [0] * len(buckets)
    for r in rows:
        d = r["days_open"] or 0
        for i, (_, lo, hi) in enumerate(buckets):
            if lo <= d <= hi:
                counts[i] += 1
                break
    return [b[0] for b in buckets], counts


@app.route("/performance")
def performance():
    conn = get_db()
    depot_stats = conn.execute(
        """SELECT depot, COUNT(*) claims, SUM(incurred) incurred,
           AVG(incurred) avg_cost, SUM(CASE WHEN closed=0 THEN 1 ELSE 0 END) open
           FROM claims GROUP BY depot ORDER BY incurred DESC"""
    ).fetchall()
    cause_stats = conn.execute(
        """SELECT cause, COUNT(*) claims, SUM(incurred) incurred
           FROM claims GROUP BY cause ORDER BY claims DESC LIMIT 6"""
    ).fetchall()
    loss_ratio_meta = get_meta(conn, "loss_ratio", {}) or {}
    conn.close()

    target = loss_ratio_meta.get("target", 65.0)
    lr_chart = build_line_chart(loss_ratio_meta.get("labels", []), loss_ratio_meta.get("loss_ratio", []), target=target)
    depot_chart = build_bar_chart([r["depot"] for r in depot_stats], [r["incurred"] or 0 for r in depot_stats])
    cause_chart = build_hbar_chart([r["cause"] for r in cause_stats], [r["incurred"] or 0 for r in cause_stats])

    return render_template(
        "performance.html", active_tab="performance",
        depot_stats=depot_stats, cause_stats=cause_stats,
        loss_ratio=loss_ratio_meta.get("overall_loss_ratio"),
        target=target,
        lr_chart=lr_chart, depot_chart=depot_chart, cause_chart=cause_chart,
        watchlist=build_watchlist(),
    )


@app.route("/explorer")
def explorer():
    conn = get_db()
    depot_names = [r["depot"] for r in conn.execute(
        "SELECT DISTINCT depot FROM vehicles ORDER BY depot"
    ).fetchall()]

    vehicle_rows = conn.execute(
        """SELECT depot, COUNT(*) vehicle_count,
           SUM(CASE WHEN status='On cover' THEN 1 ELSE 0 END) on_cover
           FROM vehicles GROUP BY depot"""
    ).fetchall()
    vehicle_by_depot = {r["depot"]: r for r in vehicle_rows}

    claim_rows = conn.execute(
        """SELECT depot, COUNT(*) claims, COALESCE(SUM(incurred),0) incurred
           FROM claims GROUP BY depot"""
    ).fetchall()
    claims_by_depot = {r["depot"]: r for r in claim_rows}
    conn.close()

    depots = []
    max_freq = 0.0
    for name in depot_names:
        v = vehicle_by_depot.get(name)
        c = claims_by_depot.get(name)
        on_cover = v["on_cover"] if v else 0
        claims = c["claims"] if c else 0
        incurred = c["incurred"] if c else 0
        freq = (claims / on_cover) if on_cover else 0
        max_freq = max(max_freq, freq)
        depots.append({
            "name": name, "on_cover": on_cover, "claims": claims,
            "incurred": incurred, "freq": freq,
            "driver_count": len(SAMPLE_DRIVERS.get(name, [])),
        })
    for d in depots:
        d["risk_pct"] = round((d["freq"] / max_freq) * 100) if max_freq else 0

    return render_template("explorer_depots.html", active_tab="explorer", depots=depots)


@app.route("/explorer/<depot>")
def explorer_depot(depot):
    conn = get_db()
    vehicles = conn.execute(
        "SELECT * FROM vehicles WHERE depot=? AND status='On cover' ORDER BY reg",
        (depot,),
    ).fetchall()
    if not vehicles and not conn.execute(
        "SELECT 1 FROM vehicles WHERE depot=? LIMIT 1", (depot,)
    ).fetchone():
        conn.close()
        return redirect(url_for("explorer"))

    claims_stats = conn.execute(
        """SELECT COUNT(*) claims, COALESCE(SUM(incurred),0) incurred,
           SUM(CASE WHEN closed=0 THEN 1 ELSE 0 END) open
           FROM claims WHERE depot=?""",
        (depot,),
    ).fetchone()
    conn.close()

    drivers = SAMPLE_DRIVERS.get(depot, [])
    tab = request.args.get("tab", "vehicles")
    return render_template(
        "explorer_depot.html", active_tab="explorer", depot=depot,
        vehicles=vehicles, claims_stats=claims_stats, drivers=drivers, tab=tab,
    )


@app.route("/explorer/<depot>/vehicle/<int:vehicle_id>")
def explorer_vehicle(depot, vehicle_id):
    conn = get_db()
    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id=? AND depot=?", (vehicle_id, depot)
    ).fetchone()
    if not vehicle:
        conn.close()
        return redirect(url_for("explorer_depot", depot=depot))
    related_claims = conn.execute(
        """SELECT * FROM claims WHERE depot=? AND vehicle_type=?
           ORDER BY loss_date DESC LIMIT 5""",
        (depot, vehicle["category"]),
    ).fetchall()
    conn.close()

    drivers = SAMPLE_DRIVERS.get(depot, [])[:2]
    return render_template(
        "explorer_vehicle.html", active_tab="explorer", depot=depot,
        vehicle=vehicle, related_claims=related_claims, drivers=drivers,
    )


@app.route("/explorer/<depot>/driver/<slug>")
def explorer_driver(depot, slug):
    driver = next((d for d in SAMPLE_DRIVERS.get(depot, []) if d["slug"] == slug), None)
    if not driver:
        return redirect(url_for("explorer_depot", depot=depot))
    return render_template(
        "explorer_driver.html", active_tab="explorer", depot=depot, driver=driver,
    )


def build_watchlist(tier="high"):
    """Fleet-wide sample drivers at a given risk tier, across all depots.

    Shared by /roadmap and /performance so both surfaces show the same
    illustrative "needs review" list rather than maintaining two copies.
    """
    out = []
    for depot, drivers in SAMPLE_DRIVERS.items():
        for d in drivers:
            if d["tier"] == tier:
                out.append({**d, "depot": depot})
    return out


@app.route("/roadmap")
def roadmap():
    return render_template("roadmap.html", active_tab="roadmap", watchlist=build_watchlist())


# Called at import time (not just under `python app.py`) so the database is
# created and seeded whether the app is started by the dev server or by
# gunicorn importing this module directly, as Render's start command does.
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
