"""ReUseMatch AI - Flask application."""
import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
from classifier import classify_image
from matching import haversine, match_items_for_need, match_needs_for_item

app = Flask(__name__)
app.config.from_object(config)
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(config.DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def run(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_db():
    with sqlite3.connect(config.DATABASE) as db:
        with open(os.path.join(config.BASE_DIR, "schema.sql")) as f:
            db.executescript(f.read())


# ---------------------------------------------------------------- helpers
@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = q("SELECT * FROM users WHERE id=?", (uid,), one=True) if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            flash("Log in to continue.", "warn")
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if not g.user["is_admin"]:
            abort(403)
        return view(*a, **kw)
    return wrapped


@app.template_filter("label")
def label(s):
    return (s or "").replace("_", " ").capitalize()


@app.context_processor
def inject():
    return {"CATEGORIES": config.CATEGORIES, "CONDITIONS": config.CONDITIONS,
            "DEFAULT_LAT": config.DEFAULT_LAT, "DEFAULT_LNG": config.DEFAULT_LNG}


def origin():
    if g.user and g.user["lat"] is not None:
        return g.user["lat"], g.user["lng"]
    return config.DEFAULT_LAT, config.DEFAULT_LNG


def with_distance(rows):
    lat, lng = origin()
    out = []
    for r in rows:
        d = dict(r)
        d["distance"] = haversine(lat, lng, r["lat"], r["lng"])
        out.append(d)
    return out


ITEM_SQL = "SELECT i.*, u.name AS donor_name FROM items i JOIN users u ON u.id = i.donor_id"


def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXT


def save_upload(file):
    ext = file.filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(config.UPLOAD_FOLDER, name))
    return name


def to_float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def impact_stats():
    rows = q("SELECT category, quantity, unit_weight_kg, collected_at FROM items WHERE status='collected'")
    kg = co2 = 0.0
    by_cat, by_month = {}, {}
    for r in rows:
        w = r["quantity"] * r["unit_weight_kg"]
        kg += w
        co2 += w * config.CO2_PER_KG.get(r["category"], 1.0)
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["quantity"]
        month = (r["collected_at"] or "")[:7] or "unknown"
        by_month[month] = by_month.get(month, 0.0) + w
    return {
        "items_reused": sum(r["quantity"] for r in rows),
        "kg": round(kg, 1),
        "co2": round(co2, 1),
        "users": q("SELECT COUNT(*) c FROM users", one=True)["c"],
        "listed": q("SELECT COUNT(*) c FROM items", one=True)["c"],
        "by_category": by_cat,
        "by_month": dict(sorted(by_month.items())),
    }


# ---------------------------------------------------------------- auth
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        email = f.get("email", "").strip().lower()
        if not f.get("name") or "@" not in email or len(f.get("password", "")) < 6:
            flash("Enter your name, a valid email, and a password of at least 6 characters.", "error")
        elif config.ALLOWED_EMAIL_DOMAIN and not email.endswith("@" + config.ALLOWED_EMAIL_DOMAIN):
            flash(f"Sign-up is limited to @{config.ALLOWED_EMAIL_DOMAIN} addresses.", "error")
        elif q("SELECT 1 FROM users WHERE email=?", (email,), one=True):
            flash("That email is already registered. Log in instead.", "error")
        else:
            uid = run(
                "INSERT INTO users(name,email,password_hash,account_type,lat,lng,area) VALUES(?,?,?,?,?,?,?)",
                (f["name"].strip(), email, generate_password_hash(f["password"]),
                 f.get("account_type", "individual"),
                 to_float(f.get("lat"), config.DEFAULT_LAT), to_float(f.get("lng"), config.DEFAULT_LNG),
                 f.get("area", "").strip()))
            session["uid"] = uid
            flash("Welcome to ReUseMatch.", "ok")
            return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE email=?", (request.form.get("email", "").strip().lower(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- public pages
@app.route("/")
def index():
    recent = with_distance(q(ITEM_SQL + " WHERE i.status='available' ORDER BY i.id DESC LIMIT 6"))
    return render_template("index.html", stats=impact_stats(), recent=recent)


@app.route("/items")
def items():
    cat, cond, term = request.args.get("category", ""), request.args.get("condition", ""), request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest")
    sql, args = ITEM_SQL + " WHERE i.status='available'", []
    if cat:
        sql += " AND i.category=?"; args.append(cat)
    if cond:
        sql += " AND i.condition=?"; args.append(cond)
    if term:
        sql += " AND (i.title LIKE ? OR i.description LIKE ?)"; args += [f"%{term}%"] * 2
    rows = with_distance(q(sql + " ORDER BY i.id DESC", args))
    if sort == "nearest":
        rows.sort(key=lambda r: r["distance"])
    return render_template("items.html", items=rows, f={"category": cat, "condition": cond, "q": term, "sort": sort})


@app.route("/items/<int:item_id>")
def item_detail(item_id):
    item = q(ITEM_SQL + " WHERE i.id=?", (item_id,), one=True) or abort(404)
    item = with_distance([item])[0]
    my_request, incoming, matches = None, [], []
    if g.user:
        my_request = q("SELECT * FROM requests WHERE item_id=? AND requester_id=? ORDER BY id DESC",
                       (item_id, g.user["id"]), one=True)
        if g.user["id"] == item["donor_id"]:
            incoming = q("SELECT r.*, u.name AS requester_name FROM requests r JOIN users u ON u.id=r.requester_id "
                         "WHERE r.item_id=? ORDER BY r.id DESC", (item_id,))
            needs = q("SELECT n.*, u.name AS user_name, u.lat, u.lng FROM needs n JOIN users u ON u.id=n.user_id "
                      "WHERE n.status='open' AND n.user_id != ?", (g.user["id"],))
            matches = match_needs_for_item(item, needs, lambda n: (n["lat"] or config.DEFAULT_LAT, n["lng"] or config.DEFAULT_LNG))[:5]
    return render_template("item_detail.html", item=item, my_request=my_request, incoming=incoming, matches=matches)


@app.route("/map")
def map_view():
    return render_template("map.html")


@app.route("/api/items")
def api_items():
    rows = q(ITEM_SQL + " WHERE i.status='available'")
    return jsonify([{"id": r["id"], "title": r["title"], "category": r["category"], "lat": r["lat"], "lng": r["lng"],
                     "quantity": r["quantity"], "url": url_for("item_detail", item_id=r["id"])} for r in rows])


@app.route("/impact")
def impact():
    return render_template("impact.html", s=impact_stats(), co2_factors=config.CO2_PER_KG, unit_w=config.UNIT_WEIGHT_KG)


# ---------------------------------------------------------------- listing
@app.route("/api/classify", methods=["POST"])
@login_required
def api_classify():
    f = request.files.get("image")
    if not f or not allowed(f.filename):
        return jsonify({"error": "Upload a PNG, JPG or WEBP image."}), 400
    return jsonify(classify_image(f.read(), f.filename))


@app.route("/items/new", methods=["GET", "POST"])
@login_required
def item_new():
    if request.method == "POST":
        f = request.form
        if not f.get("title") or f.get("category") not in config.CATEGORIES:
            flash("Add a title and choose a category.", "error")
            return render_template("item_form.html", form=f)
        image = None
        file = request.files.get("image")
        if file and file.filename:
            if not allowed(file.filename):
                flash("Photo must be PNG, JPG or WEBP.", "error")
                return render_template("item_form.html", form=f)
            image = save_upload(file)
        cat = f["category"]
        run("INSERT INTO items(donor_id,title,description,category,ai_category,ai_confidence,condition,quantity,"
            "unit_weight_kg,lat,lng,address,image) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (g.user["id"], f["title"].strip(), f.get("description", "").strip(), cat,
             f.get("ai_category") or None, to_float(f.get("ai_confidence"), None),
             f.get("condition", "good") if f.get("condition") in config.CONDITIONS else "good",
             max(1, int(to_float(f.get("quantity"), 1))),
             to_float(f.get("unit_weight_kg"), config.UNIT_WEIGHT_KG[cat]) or config.UNIT_WEIGHT_KG[cat],
             to_float(f.get("lat"), origin()[0]), to_float(f.get("lng"), origin()[1]),
             f.get("address", "").strip(), image))
        flash("Item listed. Recipients with matching needs can now find it.", "ok")
        return redirect(url_for("dashboard"))
    return render_template("item_form.html", form={})


# ---------------------------------------------------------------- requests and scheduling
@app.route("/items/<int:item_id>/request", methods=["POST"])
@login_required
def request_item(item_id):
    item = q("SELECT * FROM items WHERE id=?", (item_id,), one=True) or abort(404)
    if item["donor_id"] == g.user["id"]:
        flash("You cannot request your own item.", "error")
    elif item["status"] != "available":
        flash("This item is no longer available.", "error")
    elif q("SELECT 1 FROM requests WHERE item_id=? AND requester_id=? AND status IN ('pending','accepted')",
           (item_id, g.user["id"]), one=True):
        flash("You already have an open request for this item.", "warn")
    else:
        run("INSERT INTO requests(item_id,requester_id,message,slot) VALUES(?,?,?,?)",
            (item_id, g.user["id"], request.form.get("message", "").strip(), request.form.get("slot") or None))
        flash("Request sent. The donor will confirm a pickup time.", "ok")
    return redirect(url_for("item_detail", item_id=item_id))


@app.route("/requests/<int:req_id>/<action>", methods=["POST"])
@login_required
def request_action(req_id, action):
    r = q("SELECT * FROM requests WHERE id=?", (req_id,), one=True) or abort(404)
    item = q("SELECT * FROM items WHERE id=?", (r["item_id"],), one=True)
    is_donor, is_requester = g.user["id"] == item["donor_id"], g.user["id"] == r["requester_id"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "accept" and is_donor and r["status"] == "pending" and item["status"] == "available":
        slot = request.form.get("slot") or r["slot"]
        run("UPDATE requests SET status='accepted', slot=? WHERE id=?", (slot, req_id))
        run("UPDATE requests SET status='declined' WHERE item_id=? AND id!=? AND status='pending'", (item["id"], req_id))
        run("UPDATE items SET status='reserved' WHERE id=?", (item["id"],))
        flash("Pickup confirmed. The item is now reserved.", "ok")
    elif action == "decline" and is_donor and r["status"] == "pending":
        run("UPDATE requests SET status='declined' WHERE id=?", (req_id,))
        flash("Request declined.", "ok")
    elif action == "cancel" and (is_donor or is_requester) and r["status"] in ("pending", "accepted"):
        run("UPDATE requests SET status='cancelled' WHERE id=?", (req_id,))
        if r["status"] == "accepted":
            run("UPDATE items SET status='available' WHERE id=?", (item["id"],))
        flash("Request cancelled.", "ok")
    elif action == "collected" and is_donor and r["status"] == "accepted":
        run("UPDATE requests SET status='collected' WHERE id=?", (req_id,))
        run("UPDATE items SET status='collected', collected_at=? WHERE id=?", (now, item["id"]))
        flash("Marked as collected. It now counts toward the impact dashboard.", "ok")
    else:
        flash("That action is not available.", "error")
    return redirect(request.referrer or url_for("dashboard"))


# ---------------------------------------------------------------- needs
@app.route("/needs")
def needs():
    rows = q("SELECT n.*, u.name AS user_name, u.account_type FROM needs n JOIN users u ON u.id=n.user_id "
             "WHERE n.status='open' ORDER BY n.urgency DESC, n.id DESC")
    return render_template("needs.html", needs=rows)


@app.route("/needs/new", methods=["GET", "POST"])
@login_required
def need_new():
    if request.method == "POST":
        f = request.form
        if not f.get("title") or f.get("category") not in config.CATEGORIES:
            flash("Add a title and choose a category.", "error")
        else:
            run("INSERT INTO needs(user_id,title,description,category,quantity,urgency,min_condition) VALUES(?,?,?,?,?,?,?)",
                (g.user["id"], f["title"].strip(), f.get("description", "").strip(), f["category"],
                 max(1, int(to_float(f.get("quantity"), 1))), min(3, max(1, int(to_float(f.get("urgency"), 2)))),
                 f.get("min_condition") if f.get("min_condition") in config.CONDITIONS else "fair"))
            flash("Need posted. Matching items will appear on your dashboard.", "ok")
            return redirect(url_for("dashboard"))
    return render_template("need_form.html")


@app.route("/needs/<int:need_id>/close", methods=["POST"])
@login_required
def need_close(need_id):
    run("UPDATE needs SET status='closed' WHERE id=? AND user_id=?", (need_id, g.user["id"]))
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------- dashboard and admin
@app.route("/dashboard")
@login_required
def dashboard():
    uid = g.user["id"]
    my_items = q("SELECT * FROM items WHERE donor_id=? ORDER BY id DESC", (uid,))
    incoming = q("SELECT r.*, i.title AS item_title, u.name AS requester_name FROM requests r "
                 "JOIN items i ON i.id=r.item_id JOIN users u ON u.id=r.requester_id "
                 "WHERE i.donor_id=? AND r.status IN ('pending','accepted') ORDER BY r.id DESC", (uid,))
    outgoing = q("SELECT r.*, i.title AS item_title, i.address FROM requests r JOIN items i ON i.id=r.item_id "
                 "WHERE r.requester_id=? ORDER BY r.id DESC", (uid,))
    my_needs = q("SELECT * FROM needs WHERE user_id=? AND status='open' ORDER BY id DESC", (uid,))
    avail = q("SELECT * FROM items WHERE status='available' AND donor_id != ?", (uid,))
    lat, lng = origin()
    suggestions = [{"need": n, "top": match_items_for_need(n, avail, lat, lng)[:3]} for n in my_needs]
    return render_template("dashboard.html", my_items=my_items, incoming=incoming, outgoing=outgoing,
                           my_needs=my_needs, suggestions=suggestions)


@app.route("/admin")
@admin_required
def admin():
    rows = q(ITEM_SQL + " ORDER BY i.id DESC")
    ai = q("SELECT COUNT(*) total, SUM(category=ai_category) hit FROM items WHERE ai_category IS NOT NULL", one=True)
    acc = round(100 * ai["hit"] / ai["total"], 1) if ai["total"] else None
    return render_template("admin.html", items=rows, users=q("SELECT * FROM users ORDER BY id"),
                           ai_total=ai["total"], ai_acc=acc, stats=impact_stats())


@app.route("/admin/items/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete(item_id):
    run("DELETE FROM requests WHERE item_id=?", (item_id,))
    run("DELETE FROM items WHERE id=?", (item_id,))
    flash("Listing removed.", "ok")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
