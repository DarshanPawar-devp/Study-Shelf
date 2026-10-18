"""
StudyShelf - students.py
Everything for STUDENTS lives here, so app.py (the admin side) stays small:
  1. Student register / login / logout / password reset (Supabase Auth)
  2. Student profile (course + year) and dashboard
  3. Notifications (bell, toast, mark as read)
  4. Admin pages: Student list and Analytics
  5. Helpers app.py calls: who uploaded a note, "notify students" after an upload

These features need the Postgres database + the new tables from
migrations/001_student_features.sql. If anything is missing, enabled() is False
and the site behaves exactly like before (no student buttons are shown).
"""
import os
import re
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlencode

from flask import Blueprint, render_template, request, redirect, session, jsonify

bp = Blueprint("students", __name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")   # the PUBLIC key (safe in the browser)

ACTIVE_MINUTES = 5        # "currently active" = activity in the last 5 minutes
TOUCH_SECONDS = 60        # write last_active_at at most once a minute per student
PAGE_SIZE = 20            # rows per page on the student list

# Helper functions from app.py are stored here by init_app()
h = {}

_ready = False
_checked_at = 0.0


def init_app(app, helpers):
    h.update(helpers)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=14)   # students stay logged in
    app.register_blueprint(bp)


# ---------- Is everything set up? ----------
def enabled():
    """True only when env vars are set AND the migration has been run."""
    global _ready, _checked_at
    if _ready:
        return True
    if not (DATABASE_URL and SUPABASE_URL and ANON_KEY):
        return False
    if time.time() - _checked_at < 60:        # do not ask the database on every request
        return False
    _checked_at = time.time()
    try:
        conn = h["get_db"]()
        row = conn.execute(
            "SELECT to_regclass('public.profiles') IS NOT NULL AS a, "
            "to_regclass('public.notifications') IS NOT NULL AS b, "
            "to_regclass('public.login_events') IS NOT NULL AS c, "
            "EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' "
            "AND table_name = 'notes' AND column_name = 'uploaded_by') AS d, "
            "EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' "
            "AND table_name = 'admins' AND column_name = 'display_name') AS e"
        ).fetchone()
        conn.close()
        _ready = all(row.values())
    except Exception as error:
        print("students.enabled() check failed:", error)
        _ready = False
    return _ready


def iso(value):
    return value.isoformat() if value else None


def nice(value, with_time=False):
    if not value:
        return "Never" if with_time else "-"
    return value.strftime("%d %b %Y, %H:%M UTC" if with_time else "%d %b %Y")


def current_student():
    if not session.get("student_id") or not enabled():
        return None
    return {"id": session["student_id"], "name": session.get("student_name", "Student")}


# Every template can use {{ student }} and {{ students_enabled }}
@bp.app_context_processor
def inject_student():
    return {"students_enabled": enabled(), "student": current_student()}


# ---------- Access checks (real checks on the server, not just hidden buttons) ----------
def student_required(api=False):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not enabled():
                return (jsonify(error="Student accounts are not set up yet."), 503) if api else redirect("/")
            if not session.get("student_id"):
                return (jsonify(error="Please log in."), 401) if api else redirect("/student/login")
            return view(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(api=False):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not h["is_admin"]():
                return (jsonify(error="Admin only"), 403) if api else redirect("/login")
            if not enabled():
                return (jsonify(error="Student features are not set up yet."), 503) if api else render_template(
                    "student_auth.html", mode="setup")
            return view(*args, **kwargs)
        return wrapper
    return decorator


# ---------- Last active (heartbeat), at most once a minute ----------
@bp.before_app_request
def touch_last_active():
    if request.endpoint in (None, "static") or not session.get("student_id"):
        return
    if time.time() - session.get("touched", 0) < TOUCH_SECONDS or not enabled():
        return
    try:
        conn = h["get_db"]()
        conn.execute("UPDATE profiles SET last_active_at = now() WHERE id = ?::uuid", (session["student_id"],))
        conn.commit()
        conn.close()
        session["touched"] = time.time()
    except Exception as error:
        print("touch_last_active failed:", error)


# ---------- Supabase Auth (called from the server) ----------
def auth_call(path, payload, query=None):
    """Returns (http_status, json). Status 0 means we could not reach Supabase."""
    import requests
    try:
        response = requests.post(
            SUPABASE_URL + "/auth/v1/" + path, params=query, json=payload, timeout=20,
            headers={"apikey": ANON_KEY, "Content-Type": "application/json"})
    except requests.RequestException:
        return 0, {}
    try:
        data = response.json()
    except ValueError:
        data = {}
    return response.status_code, data


def auth_error_text(status, data):
    code = str(data.get("error_code") or data.get("code") or "")
    if status == 0:
        return "Could not reach the login service. Please try again."
    if code == "invalid_credentials":
        return "Wrong email or password."
    if code == "email_not_confirmed":
        return "Please confirm your email first. Check your inbox."
    if code in ("user_already_exists", "email_exists"):
        return "An account with this email already exists. Try logging in."
    if code == "weak_password":
        return "That password is too weak. Use a longer one."
    if status == 429 or "rate_limit" in code:
        return "Too many requests right now. Please wait a few minutes."
    return "Something went wrong. Please try again."


EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def start_session(user_id, name):
    session.pop("is_admin", None)        # a browser is a student OR an admin, never both
    session.pop("admin_user", None)
    session["student_id"] = str(user_id)
    session["student_name"] = name
    session["touched"] = time.time()
    session.permanent = True


def clean_year(course, year):
    """Returns a valid year code for that course, or None (= all years)."""
    courses = h["get_courses"]()
    if course in courses and year in [y["code"] for y in h["years_for"](courses[course]["years"])]:
        return year
    return None


def auth_page(mode, status=200, **extra):
    courses = h["get_courses"]()
    return render_template(
        "student_auth.html", mode=mode, courses=courses, years_order=h["year_codes"],
        year_names=h["year_names"], supabase_url=SUPABASE_URL, anon_key=ANON_KEY, **extra), status


# ---------- 1. Register / login / logout / reset ----------
@bp.route("/student/register", methods=["GET", "POST"])
def register():
    if not enabled():
        return auth_page("setup", 503)
    if session.get("student_id"):
        return redirect("/dashboard")
    if request.method == "GET":
        return auth_page("register")

    name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    course = request.form.get("course", "").strip().upper()
    year = clean_year(course, request.form.get("year", ""))
    form = {"full_name": name, "email": email, "course": course, "year": year or ""}

    error = None
    if not name or len(name) > 80:
        error = "Please enter your name (up to 80 characters)."
    elif not EMAIL_RE.match(email):
        error = "Please enter a valid email address."
    elif len(password) < 8 or len(password) > 72:
        error = "Password must be 8 to 72 characters."
    elif course not in h["get_courses"]():
        error = "Please choose your course."
    if error:
        return auth_page("register", 400, error=error, form=form)

    status, data = auth_call("signup", {"email": email, "password": password, "data": {"full_name": name}})
    user = data.get("user") or data
    if status >= 400:
        return auth_page("register", 400, error=auth_error_text(status, data), form=form)
    # With email confirmation on, Supabase answers "ok" for an existing email but returns no identities
    if not user.get("id") or user.get("identities") == []:
        return auth_page("register", 400, error="An account with this email already exists. Try logging in.", form=form)

    try:
        conn = h["get_db"]()
        conn.execute(
            "INSERT INTO profiles (id, full_name, course, year) VALUES (?::uuid, ?, ?, ?) "
            "ON CONFLICT (id) DO NOTHING", (user["id"], name, course, year))
        conn.commit()
        conn.close()
    except Exception as error_:
        print("profile insert failed:", error_)
        return auth_page("register", 500, error="Your account was created but your profile could not be saved. Please log in.", form=form)

    if data.get("access_token"):          # email confirmation is OFF in Supabase: log in straight away
        record_login(user["id"])
        start_session(user["id"], name)
        return redirect("/dashboard")
    return auth_page("login", 200, success="Account created. Please confirm your email, then log in.")


def record_login(user_id):
    conn = h["get_db"]()
    conn.execute("INSERT INTO login_events (user_id) VALUES (?::uuid)", (user_id,))
    conn.execute("UPDATE profiles SET last_active_at = now() WHERE id = ?::uuid", (user_id,))
    conn.commit()
    conn.close()


@bp.route("/student/login", methods=["GET", "POST"])
def login():
    if not enabled():
        return auth_page("setup", 503)
    if session.get("student_id"):
        return redirect("/dashboard")
    if request.method == "GET":
        return auth_page("login")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    ip = "student:" + h["visitor_ip"]()          # same lock-out idea as the admin login

    conn = h["get_db"]()
    if h["too_many_failures"](conn, ip):
        conn.commit()
        conn.close()
        return auth_page("login", 429, error="Too many wrong tries. Please wait 10 minutes.", form={"email": email})

    status, data = auth_call("token", {"email": email, "password": password}, {"grant_type": "password"})
    user = data.get("user") or {}
    if status != 200 or not user.get("id"):
        if status in (400, 401, 422):
            conn.execute("INSERT INTO login_attempts (ip, attempted_at) VALUES (?, ?)", (ip, h["time_text"]()))
        conn.commit()
        conn.close()
        return auth_page("login", 401, error=auth_error_text(status, data), form={"email": email})

    conn.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))
    # A student without a profile row (rare) gets one now; the course is chosen on the dashboard
    meta_name = str((user.get("user_metadata") or {}).get("full_name") or "Student").strip()[:80] or "Student"
    conn.execute("INSERT INTO profiles (id, full_name) VALUES (?::uuid, ?) ON CONFLICT (id) DO NOTHING",
                 (user["id"], meta_name))
    name = conn.execute("SELECT full_name FROM profiles WHERE id = ?::uuid", (user["id"],)).fetchone()["full_name"]
    conn.commit()
    conn.close()

    record_login(user["id"])
    start_session(user["id"], name)
    return redirect("/dashboard")


@bp.route("/student/logout")
def logout():
    session.clear()
    return redirect("/")


@bp.route("/student/forgot", methods=["GET", "POST"])
def forgot():
    if not enabled():
        return auth_page("setup", 503)
    if request.method == "GET":
        return auth_page("forgot")
    email = request.form.get("email", "").strip().lower()
    if EMAIL_RE.match(email):
        base = (os.environ.get("SITE_URL") or request.url_root).rstrip("/")
        if h["on_vercel"] and base.startswith("http://"):
            base = "https://" + base[len("http://"):]
        auth_call("recover", {"email": email}, {"redirect_to": base + "/student/reset"})
    # Always the same answer, so nobody can find out which emails have accounts
    return auth_page("forgot", 200, success="If that email has an account, a reset link is on its way.")


@bp.route("/student/reset")
def reset():
    if not enabled():
        return auth_page("setup", 503)
    return auth_page("reset")


# ---------- 2. Dashboard + profile ----------
def my_unread(conn, user_id):
    return conn.execute("SELECT COUNT(*) AS n FROM notifications WHERE user_id = ?::uuid AND read_at IS NULL",
                        (user_id,)).fetchone()["n"]


def my_notifications(conn, user_id, limit):
    rows = conn.execute(
        "SELECT n.id, n.note_id, n.created_at, n.read_at, t.title, t.subject, t.course, t.year "
        "FROM notifications n JOIN notes t ON t.id = n.note_id "
        "WHERE n.user_id = ?::uuid ORDER BY n.created_at DESC, n.id DESC LIMIT ?", (user_id, limit)).fetchall()
    return [{"id": r["id"], "note_id": r["note_id"], "created_at": iso(r["created_at"]),
             "read": r["read_at"] is not None, "title": r["title"], "subject": r["subject"],
             "course": r["course"], "year": r["year"]} for r in rows]


@bp.route("/dashboard")
@student_required()
def dashboard():
    uid = session["student_id"]
    conn = h["get_db"]()
    profile = conn.execute("SELECT full_name, course, year, created_at FROM profiles WHERE id = ?::uuid", (uid,)).fetchone()
    if not profile:
        conn.close()
        session.clear()
        return redirect("/student/login")
    courses = h["get_courses"]()
    info = courses.get(profile["course"])
    note_count = None
    if profile["course"]:
        note_count = conn.execute("SELECT COUNT(*) AS n FROM notes WHERE course = ?", (profile["course"],)).fetchone()["n"]
    unread = my_unread(conn, uid)
    recent = my_notifications(conn, uid, 5)
    conn.close()
    return render_template(
        "dashboard.html", profile=profile, course_info=info, note_count=note_count, unread=unread,
        recent=recent, courses=courses, years_order=h["year_codes"], year_names=h["year_names"],
        years=h["years_for"](info["years"]) if info else [])


@bp.route("/api/profile", methods=["PUT"])
@student_required(api=True)
def update_profile():
    data = request.get_json(silent=True) or {}
    name = str(data.get("full_name", "")).strip()
    course = str(data.get("course", "")).strip().upper()
    if not name or len(name) > 80:
        return {"error": "Please enter your name (up to 80 characters)."}, 400
    if course not in h["get_courses"]():
        return {"error": "Please choose a valid course."}, 400
    year = clean_year(course, str(data.get("year", "")))
    # The row is chosen by the logged-in session, never by an id sent from the browser
    conn = h["get_db"]()
    conn.execute("UPDATE profiles SET full_name = ?, course = ?, year = ? WHERE id = ?::uuid",
                 (name, course, year, session["student_id"]))
    conn.commit()
    conn.close()
    session["student_name"] = name
    return jsonify(ok=True)


# ---------- 3. Notifications ----------
@bp.route("/api/notifications")
@student_required(api=True)
def api_notifications():
    uid = session["student_id"]
    conn = h["get_db"]()
    unread = my_unread(conn, uid)
    latest = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM notifications WHERE user_id = ?::uuid", (uid,)).fetchone()["m"]
    items = my_notifications(conn, uid, 15)
    conn.close()
    return jsonify(unread=unread, latest_id=latest, items=items)


@bp.route("/api/notifications/read-all", methods=["POST"])
@student_required(api=True)
def read_all():
    conn = h["get_db"]()
    conn.execute("UPDATE notifications SET read_at = now() WHERE user_id = ?::uuid AND read_at IS NULL", (session["student_id"],))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@bp.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
@student_required(api=True)
def read_one(notification_id):
    conn = h["get_db"]()
    # "AND user_id = me" means a student cannot touch somebody else's notification
    conn.execute("UPDATE notifications SET read_at = COALESCE(read_at, now()) WHERE id = ? AND user_id = ?::uuid",
                 (notification_id, session["student_id"]))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@bp.route("/notifications")
@student_required()
def notifications_page():
    conn = h["get_db"]()
    items = my_notifications(conn, session["student_id"], 50)
    unread = my_unread(conn, session["student_id"])
    conn.close()
    return render_template("notifications.html", items=items, unread=unread)


def notify_students(note_id, course, year):
    """Called by app.py after an admin saved a note.
    The course and year come from the saved note (validated by the server), never from the browser.
    Only students (rows in profiles) are notified, so the admin is never a recipient.
    ON CONFLICT DO NOTHING + UNIQUE(user_id, note_id) = no duplicates, even if this runs twice."""
    try:
        conn = h["get_db"]()
        conn.execute(
            "INSERT INTO notifications (user_id, note_id) "
            "SELECT id, ?::integer FROM profiles WHERE course = ? AND (year IS NULL OR year = ?) "
            "ON CONFLICT (user_id, note_id) DO NOTHING", (note_id, course, year))
        conn.commit()
        conn.close()
    except Exception as error:
        print("notify_students failed (the note itself was saved):", error)


# ---------- Uploader helpers used by app.py ----------
def admin_id(conn, username):
    row = conn.execute("SELECT id FROM admins WHERE username = ?", (username,)).fetchone()
    return row["id"] if row else None


def notes_with_uploader(conn, course=""):
    sql = ("SELECT n.*, COALESCE(a.display_name, CASE WHEN a.id IS NOT NULL THEN 'Admin' END) AS uploader_name "
           "FROM notes n LEFT JOIN admins a ON a.id = n.uploaded_by ")
    if course:
        rows = conn.execute(sql + "WHERE n.course = ? ORDER BY n.id DESC", (course,)).fetchall()
    else:
        rows = conn.execute(sql + "ORDER BY n.id DESC").fetchall()
    for row in rows:
        row.pop("uploaded_by", None)      # the internal admin id is not sent to visitors
    return rows


def display_names():
    if not enabled():
        return {}
    conn = h["get_db"]()
    rows = conn.execute("SELECT username, display_name FROM admins").fetchall()
    conn.close()
    return {r["username"]: r["display_name"] for r in rows if r["display_name"]}


@bp.route("/api/admins/<username>/display-name", methods=["PUT"])
def set_display_name(username):
    if not h["is_admin"]():
        return {"error": "Admin only"}, 403
    username = username.lower()
    if not h["can_edit_admin"](username):
        return {"error": "Only the owner can change another admin's display name."}, 403
    if not enabled():
        return {"error": "Student features are not set up yet."}, 503
    name = str((request.get_json(silent=True) or {}).get("display_name", "")).strip()
    if len(name) > 40:
        return {"error": "Display name can be up to 40 characters."}, 400
    conn = h["get_db"]()
    cursor = conn.execute("UPDATE admins SET display_name = ? WHERE username = ?", (name or None, username))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return {"error": "Admin not found."}, 404
    return jsonify(ok=True)


# ---------- 4a. Admin: student list ----------
@bp.route("/students")
@admin_required()
def student_list():
    q = request.args.get("q", "").strip()[:80]
    course = request.args.get("course", "").strip().upper()
    sort = request.args.get("sort", "registered")
    direction = "ASC" if request.args.get("dir") == "asc" else "DESC"
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    where, params = [], []
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(p.full_name ILIKE ? OR u.email ILIKE ?)")
        params += [like, like]
    if course == "NONE":
        where.append("p.course IS NULL")
    elif course:
        where.append("p.course = ?")
        params.append(course)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # The ORDER BY text comes from this fixed list, never from the browser
    order_sql = {"registered": "p.created_at " + direction,
                 "active": "p.last_active_at " + direction + " NULLS LAST",
                 "name": "p.full_name " + direction}.get(sort, "p.created_at DESC")

    conn = h["get_db"]()
    total = conn.execute("SELECT COUNT(*) AS n FROM profiles p JOIN auth.users u ON u.id = p.id " + where_sql,
                         params).fetchone()["n"]
    rows = conn.execute(
        "SELECT p.full_name, u.email, p.course, p.year, p.created_at, p.last_active_at, "
        "(u.email_confirmed_at IS NOT NULL) AS verified, "
        "(u.banned_until IS NOT NULL AND u.banned_until > now()) AS banned "
        "FROM profiles p JOIN auth.users u ON u.id = p.id " + where_sql +
        " ORDER BY " + order_sql + " LIMIT ? OFFSET ?", params + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
    conn.close()

    students = [{
        "name": r["full_name"], "email": r["email"], "course": r["course"] or "Not selected",
        "year": r["year"] or "", "registered": nice(r["created_at"]),
        "last_active": nice(r["last_active_at"], True),
        "status": "Suspended" if r["banned"] else ("Verified" if r["verified"] else "Email not confirmed"),
    } for r in rows]

    base_query = urlencode({"q": q, "course": course, "sort": sort, "dir": direction.lower()})
    pages = max(1, -(-total // PAGE_SIZE))
    return render_template("students.html", students=students, total=total, page=page, pages=pages,
                           q=q, course=course, sort=sort, direction=direction.lower(),
                           base_query=base_query, courses=h["get_courses"]())


# ---------- 4b. Admin: analytics ----------
@bp.route("/analytics")
@admin_required()
def analytics_page():
    return render_template("analytics.html")


@bp.route("/api/analytics")
@admin_required(api=True)
def api_analytics():
    days = 30 if request.args.get("days") == "30" else 7
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)     # all dates are UTC
    start = today - timedelta(days=days - 1)

    conn = h["get_db"]()

    def number(sql, params=()):
        return conn.execute(sql, params).fetchone()["n"]

    total = number("SELECT COUNT(*) AS n FROM profiles")
    active_now = number("SELECT COUNT(*) AS n FROM profiles WHERE last_active_at >= ?",
                        (now - timedelta(minutes=ACTIVE_MINUTES),))
    unique_today = number("SELECT COUNT(DISTINCT user_id) AS n FROM login_events WHERE created_at >= ?", (today,))
    logins_period = number("SELECT COUNT(*) AS n FROM login_events WHERE created_at >= ?", (start,))
    unique_period = number("SELECT COUNT(DISTINCT user_id) AS n FROM login_events WHERE created_at >= ?", (start,))
    new_period = number("SELECT COUNT(*) AS n FROM profiles WHERE created_at >= ?", (start,))

    login_rows = {r["d"]: r for r in conn.execute(
        "SELECT (created_at AT TIME ZONE 'UTC')::date AS d, COUNT(*) AS logins, COUNT(DISTINCT user_id) AS users "
        "FROM login_events WHERE created_at >= ? GROUP BY 1", (start,)).fetchall()}
    signup_rows = {r["d"]: r["n"] for r in conn.execute(
        "SELECT (created_at AT TIME ZONE 'UTC')::date AS d, COUNT(*) AS n "
        "FROM profiles WHERE created_at >= ? GROUP BY 1", (start,)).fetchall()}
    course_rows = conn.execute(
        "SELECT COALESCE(course, 'Not selected') AS c, COUNT(*) AS n FROM profiles GROUP BY 1 ORDER BY 2 DESC").fetchall()
    first_login = conn.execute("SELECT MIN(created_at) AS m FROM login_events").fetchone()["m"]
    conn.close()

    labels = [(start + timedelta(days=i)).date() for i in range(days)]
    return jsonify(
        days=days, from_date=labels[0].isoformat(), to_date=labels[-1].isoformat(),
        tracking_since=iso(first_login), active_minutes=ACTIVE_MINUTES,
        cards={"total_students": total, "active_now": active_now, "unique_today": unique_today,
               "logins_period": logins_period, "unique_period": unique_period, "new_period": new_period},
        labels=[d.isoformat() for d in labels],
        daily_active=[(login_rows[d]["users"] if d in login_rows else 0) for d in labels],
        logins=[(login_rows[d]["logins"] if d in login_rows else 0) for d in labels],
        signups=[signup_rows.get(d, 0) for d in labels],
        courses=[{"course": r["c"], "students": r["n"]} for r in course_rows])
