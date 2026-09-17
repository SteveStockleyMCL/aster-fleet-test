import sys
import os
import json
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

    conn.close()
    return render_template(
        "claims.html",
        active_tab="claims",
        rows=rows, q=q, depot=depot, depots=depots, period=period, basis=basis,
        sort_key=sort_key, sort_dir=sort_dir,
        total_claims=total_claims, total_incurred=total_incurred,
        open_claims=open_claims, closed_claims=closed_claims, avg_cost=avg_cost,
        ccpv=ccpv, overall_lr=overall_lr, target=target, cur_lr=cur_lr, prior_lr=prior_lr,
        current_py=current_py, prior_py=prior_py,
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
