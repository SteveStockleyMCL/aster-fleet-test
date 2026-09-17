import sys
import os
import json
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db, init_db, get_meta, DB_PATH

from flask import Flask, render_template, request, redirect, url_for, flash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, "templates"),
    static_folder=os.path.join(PROJECT_ROOT, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "aster-test-build-dev-secret")

CATEGORIES = [
    "Artic HGV", "Rigid HGV", "7.5T Rigid", "Transit Van", "Sprinter Van", "Pickup",
]


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
    return render_template(
        "performance.html", active_tab="performance",
        depot_stats=depot_stats, cause_stats=cause_stats,
        loss_ratio=loss_ratio_meta.get("overall_loss_ratio"),
        target=loss_ratio_meta.get("target", 65.0),
    )


# Called at import time (not just under `python app.py`) so the database is
# created and seeded whether the app is started by the dev server or by
# gunicorn importing this module directly, as Render's start command does.
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
