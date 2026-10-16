import os
import re
import sys
import time
from datetime import datetime
import sqlite3
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# The css/js files live in the "static" folder next to this file, so the app
# itself serves them (the web address is /static/...).
app = Flask(__name__, static_folder="static", static_url_path="/static")

# True when the site is running online on Vercel (Vercel sets this variable)
ON_VERCEL = bool(os.environ.get("VERCEL"))

# ---------- Admin accounts ----------
# needed to remember who is logged in
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key")
if ON_VERCEL and app.secret_key == "dev-only-key":
    raise RuntimeError("Set the SECRET_KEY environment variable in Vercel first.")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = ON_VERCEL      # online the login cookie only travels over https

# Vercel cannot receive requests bigger than about 4.5 MB, so uploads are limited to 4 MB online
MAX_UPLOAD_MB = 4 if ON_VERCEL else 0                 # 0 = no limit (your own computer)
if ON_VERCEL:
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


@app.errorhandler(413)
def file_too_big(error):
    return {"error": "The file is too big. The maximum size is " + str(MAX_UPLOAD_MB) + " MB."}, 413

# Admin accounts live in the database (the "admins" table), so you can give each
# teacher their own login from the website: log in, then choose "Manage admins".
#
# ADMIN_USER and ADMIN_PASS are used only ONCE: the first time the app starts
# with a database that has no admins yet, they become the first admin account.
# Changing them later has no effect. Use the website instead.
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "change-me")

# ---------- Online services (Supabase) ----------
# On your own computer none of these are needed: the app uses the notes.db file and
# the uploads folder. Online, set them and the app switches to Supabase automatically.
#   DATABASE_URL         Supabase Postgres connection string (the database)
#   SUPABASE_URL         your project address, e.g. https://abcd1234.supabase.co
#   SUPABASE_SERVICE_KEY the secret "service_role" key (keep it private!)
#   SUPABASE_BUCKET      name of a PUBLIC storage bucket (default: notes)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "notes")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)


# ---------- Courses ----------
# Courses are stored in the database and managed from the website:
# log in as admin, choose "Manage courses", then add, edit or delete courses.
#
# The list below is only used ONCE, the very first time the app starts with
# a new database, so the site is not empty. Changing it later has no effect
# on an existing notes.db. Use the website instead.
DEFAULT_COURSES = [
    ("BCA",  "Bachelor of Computer Applications",  3),
    ("BBA",  "Bachelor of Business Administration", 3),
    ("BMS",  "Bachelor of Management Studies",      3),
    ("MCA",  "Master of Computer Applications",     2),
    ("IMCA", "Integrated MCA",                      5),
]

# Year codes in order. A 3-year course uses FY, SY, TY.
# A 5-year course uses FY, SY, TY, 4Y, 5Y. The most a course can have is 6.
YEAR_CODES = ["FY", "SY", "TY", "4Y", "5Y", "6Y"]
YEAR_NAMES = {
    "FY": "First Year", "SY": "Second Year", "TY": "Third Year",
    "4Y": "Fourth Year", "5Y": "Fifth Year", "6Y": "Sixth Year",
}


# Returns the years of a course that is "count" years long, e.g. 3 -> FY, SY, TY
def years_for(count):
    count = max(1, min(int(count), len(YEAR_CODES)))
    return [{"code": c, "name": YEAR_NAMES[c]} for c in YEAR_CODES[:count]]


# ---------- Cache busting ----------
# Adds ?v=<last-changed-time> to every static link so the browser
# downloads the new file as soon as it changes.
def dated_url_for(endpoint, **values):
    if endpoint == "static" and values.get("filename"):
        file_path = os.path.join(app.static_folder, values["filename"])
        if os.path.isfile(file_path):
            values["v"] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)


@app.context_processor
def use_dated_url_for():
    return dict(url_for=dated_url_for)


# ---------- TEMPORARY DEBUG (remove after fixing) ----------
# Shows the real error on the page instead of "Internal Server Error".
@app.errorhandler(Exception)
def show_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    text = traceback.format_exc()
    for secret in (DATABASE_URL, os.environ.get("SUPABASE_SERVICE_KEY", ""), os.environ.get("SECRET_KEY", ""), ADMIN_PASS):
        if secret:
            text = text.replace(secret, "***")
    try:
        from urllib.parse import urlparse, unquote
        pw = urlparse(DATABASE_URL).password
        if pw:
            text = text.replace(pw, "***").replace(unquote(pw), "***")
    except Exception:
        pass
    return "<pre style='white-space:pre-wrap'>" + text.replace("<", "&lt;") + "</pre>", 500


# ---------- Uploaded files ----------
# On your computer the files go to static/uploads.
# Online (Supabase) they go to the storage bucket, because Vercel cannot keep files.
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
if not USE_SUPABASE:
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    except OSError:
        pass


# The address where a stored file can be opened
def file_url(filename):
    if USE_SUPABASE:
        return SUPABASE_URL + "/storage/v1/object/public/" + SUPABASE_BUCKET + "/" + quote(filename)
    return "/static/uploads/" + filename


# Keeps a file. "data" is the file content (bytes).
def save_upload(filename, data, content_type="application/octet-stream"):
    if USE_SUPABASE:
        import requests
        response = requests.post(
            SUPABASE_URL + "/storage/v1/object/" + SUPABASE_BUCKET + "/" + quote(filename),
            headers={"Authorization": "Bearer " + SUPABASE_KEY, "apikey": SUPABASE_KEY,
                     "Content-Type": content_type or "application/octet-stream"},
            data=data, timeout=60)
        response.raise_for_status()
    else:
        with open(os.path.join(UPLOAD_FOLDER, os.path.basename(filename)), "wb") as f:
            f.write(data)


# Removes a stored file. A file that is already gone is not a problem.
def delete_upload(filename):
    if not filename:
        return
    try:
        if USE_SUPABASE:
            import requests
            requests.delete(
                SUPABASE_URL + "/storage/v1/object/" + SUPABASE_BUCKET + "/" + quote(filename),
                headers={"Authorization": "Bearer " + SUPABASE_KEY, "apikey": SUPABASE_KEY},
                timeout=30)
        else:
            os.remove(os.path.join(UPLOAD_FOLDER, os.path.basename(filename)))
    except Exception:
        pass   # the file was already gone


# ---------- Database ----------
# Your computer: the notes.db file (SQLite).
# Online: Supabase Postgres, used when DATABASE_URL is set.
# Both speak SQL. The only difference is that SQLite writes "?" for a value and
# Postgres writes "%s", so PgConnection changes the "?" for us.
class PgConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace("?", "%s"), params)

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


# Makes the first admin when there is none yet, and makes sure someone is the owner
def seed_first_admin(conn):
    if not conn.execute("SELECT 1 FROM admins LIMIT 1").fetchone():
        if ON_VERCEL and ADMIN_PASS == "change-me":
            raise RuntimeError("Set ADMIN_USER and ADMIN_PASS in Vercel before the first start.")
        conn.execute(
            "INSERT INTO admins (username, password_hash, created_at, is_owner) VALUES (?, ?, ?, 1) "
            "ON CONFLICT (username) DO NOTHING",
            (ADMIN_USER.strip().lower(), generate_password_hash(ADMIN_PASS),
             datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
    # Older databases have no owner yet: the oldest admin becomes the owner
    if not conn.execute("SELECT 1 FROM admins WHERE is_owner = 1").fetchone():
        conn.execute("UPDATE admins SET is_owner = 1 WHERE username = "
                     "(SELECT username FROM admins ORDER BY created_at, username LIMIT 1)")


# Postgres: create the tables once each time the server starts (not on every request,
# because every step is a trip over the internet)
postgres_ready = False


def setup_postgres(conn):
    had_courses_table = conn.execute("SELECT to_regclass('public.courses')::text AS t").fetchone()["t"]

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            title TEXT,
            year TEXT,
            subject TEXT,
            unit TEXT,
            description TEXT,
            filename TEXT,
            created_at TEXT,
            course TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            years INTEGER NOT NULL,
            position INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT,
            is_owner INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Supabase also opens every table to the internet through its own API.
    # Turning on row level security (with no rules) closes that door. This app
    # connects with the owner login, which is not affected.
    for table in ("notes", "courses", "admins"):
        conn.execute("ALTER TABLE " + table + " ENABLE ROW LEVEL SECURITY")

    if not had_courses_table:
        for position, (code, name, years) in enumerate(DEFAULT_COURSES):
            conn.execute(
                "INSERT INTO courses (code, name, years, position) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (code) DO NOTHING",
                (code, name, years, position)
            )

    seed_first_admin(conn)
    conn.commit()


# Connect to the database.
# The SQLite tables are created here if they are missing, so deleting notes.db
# can never break the app: a fresh empty database is made automatically.
def get_db():
    global postgres_ready

    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row
        # prepare_threshold=None is needed for the Supabase connection pooler
        conn = PgConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None))
        if not postgres_ready:
            setup_postgres(conn)
            postgres_ready = True
        return conn

    conn = sqlite3.connect(os.path.join(app.root_path, "notes.db"))
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            year TEXT,
            subject TEXT,
            unit TEXT,
            description TEXT,
            filename TEXT,
            created_at TEXT
        )
    """)

    # The courses table. When it is created for the first time we fill it
    # with DEFAULT_COURSES. After that the admin manages it from the website,
    # so we never refill it (even if the admin deletes every course).
    had_courses_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'courses'"
    ).fetchone()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            years INTEGER NOT NULL,
            position INTEGER NOT NULL
        )
    """)
    if not had_courses_table:
        for position, (code, name, years) in enumerate(DEFAULT_COURSES):
            conn.execute(
                "INSERT INTO courses (code, name, years, position) VALUES (?, ?, ?, ?)",
                (code, name, years, position)
            )

    # The admins table. Passwords are stored as hashes, never as plain text.
    # is_owner = 1 marks the ONE owner. Only the owner can add or delete admins
    # and change other admins. Other admins can only change their own account.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT,
            is_owner INTEGER NOT NULL DEFAULT 0
        )
    """)
    admin_columns = [row[1] for row in conn.execute("PRAGMA table_info(admins)").fetchall()]
    if "is_owner" not in admin_columns:
        conn.execute("ALTER TABLE admins ADD COLUMN is_owner INTEGER NOT NULL DEFAULT 0")

    # When the table is empty, the first admin is made from ADMIN_USER / ADMIN_PASS
    # and becomes the owner.
    seed_first_admin(conn)

    # Older databases have no date column yet, so add it once
    columns = [row[1] for row in conn.execute("PRAGMA table_info(notes)").fetchall()]
    if "created_at" not in columns:
        conn.execute("ALTER TABLE notes ADD COLUMN created_at TEXT")

    # Older databases have no course column either, so add it once.
    # Notes saved before courses existed are placed under the first course.
    if "course" not in columns:
        conn.execute("ALTER TABLE notes ADD COLUMN course TEXT")
    first = conn.execute("SELECT code FROM courses ORDER BY position, code LIMIT 1").fetchone()
    if first:
        conn.execute("UPDATE notes SET course = ? WHERE course IS NULL OR course = ''", (first["code"],))

    conn.commit()
    return conn


# Reads all courses from the database, in order: {"BCA": {"name": ..., "years": 3}, ...}
def get_courses():
    conn = get_db()
    rows = conn.execute("SELECT code, name, years FROM courses ORDER BY position, code").fetchall()
    conn.close()
    return {row["code"]: {"name": row["name"], "years": row["years"]} for row in rows}


# Checks the admin session. Used by the course management routes.
def is_admin():
    return bool(session.get("is_admin"))


# True when the logged-in admin is the owner (checked in the database every time)
def is_owner():
    if not is_admin():
        return False
    conn = get_db()
    row = conn.execute("SELECT is_owner FROM admins WHERE username = ?",
                       (session.get("admin_user"),)).fetchone()
    conn.close()
    return bool(row and row["is_owner"])


# The owner may change any admin. Other admins may only change themselves.
def can_edit_admin(username):
    return is_owner() or username == session.get("admin_user")


# Step 1: the first page. Asks "Student or Admin?"
@app.route("/")
def home():
    return render_template("role.html", is_admin=session.get("is_admin", False))


# "Student" button: make sure no admin session is active, then pick a course
@app.route("/student")
def student():
    session.pop("is_admin", None)
    session.pop("admin_user", None)
    return redirect("/courses")


# Step 2: choose a course (students and the logged-in admin both land here)
@app.route("/courses")
def courses():
    return render_template("courses.html", courses=get_courses(), is_admin=session.get("is_admin", False))


# Step 3: one course. Shows that course's years, then its notes.
@app.route("/course/<code>")
def course_page(code):
    code = code.upper()
    courses = get_courses()
    if code not in courses:
        return redirect("/courses")   # unknown course, go back to the list

    return render_template(
        "index.html",
        is_admin=session.get("is_admin", False),
        course_code=code,
        course=courses[code],
        years=years_for(courses[code]["years"]),
        show_add=True,          # the header shows the "Add Note" button (admin only)
        max_upload_mb=MAX_UPLOAD_MB,
    )


# Show the login page (GET) and check the details (POST)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        admin = conn.execute("SELECT password_hash FROM admins WHERE username = ?", (username,)).fetchone()
        conn.close()

        if admin and check_password_hash(admin["password_hash"], password):
            session["is_admin"] = True        # remember that the admin is logged in
            session["admin_user"] = username  # and which admin it is
            return redirect("/courses")       # next step: choose a course
        else:
            return redirect("/login?error=1") # wrong details, show the error

    if session.get("is_admin"):
        return redirect("/courses")           # already logged in

    return render_template("login.html")


# Log out by clearing the memory
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- Manage courses (admin only) ----------

# The management page: a list of courses with Add / Edit / Delete
@app.route("/manage")
def manage():
    if not is_admin():
        return redirect("/login")

    # how many notes each course has (shown in the list)
    conn = get_db()
    counts = {row["course"]: row["total"] for row in
              conn.execute("SELECT course, COUNT(*) AS total FROM notes GROUP BY course").fetchall()}
    conn.close()

    return render_template("manage.html", courses=get_courses(), counts=counts, is_admin=True,
                           max_years=len(YEAR_CODES))


# Checks the name and years sent from the form. Returns (name, years, error).
def read_course_fields(data):
    name = str(data.get("name", "")).strip()
    try:
        years = int(data.get("years"))
    except (TypeError, ValueError):
        years = 0

    if not name or len(name) > 60:
        return None, None, "Course name is required (up to 60 characters)."
    if years < 1 or years > len(YEAR_CODES):
        return None, None, "Years must be between 1 and " + str(len(YEAR_CODES)) + "."
    return name, years, None


# Add a course
@app.route("/api/courses", methods=["POST"])
def add_course():
    if not is_admin():
        return {"error": "Admin only"}, 403

    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()
    name, years, error = read_course_fields(data)

    if not re.fullmatch(r"[A-Z0-9]{2,10}", code):
        return {"error": "Code must be 2 to 10 letters or numbers, e.g. BCA."}, 400
    if error:
        return {"error": error}, 400

    conn = get_db()
    if conn.execute("SELECT 1 FROM courses WHERE code = ?", (code,)).fetchone():
        conn.close()
        return {"error": code + " already exists."}, 409

    # new courses go to the end of the list
    last = conn.execute("SELECT COALESCE(MAX(position), -1) AS p FROM courses").fetchone()["p"]
    conn.execute("INSERT INTO courses (code, name, years, position) VALUES (?, ?, ?, ?)",
                 (code, name, years, last + 1))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# Edit a course (the name and the number of years; the code stays the same)
@app.route("/api/courses/<code>", methods=["PUT"])
def edit_course(code):
    if not is_admin():
        return {"error": "Admin only"}, 403

    code = code.upper()
    name, years, error = read_course_fields(request.get_json(silent=True) or {})
    if error:
        return {"error": error}, 400

    conn = get_db()
    course = conn.execute("SELECT years FROM courses WHERE code = ?", (code,)).fetchone()
    if not course:
        conn.close()
        return {"error": "Course not found."}, 404

    # Do not cut years that still have notes, or those notes would vanish from the site
    if years < course["years"]:
        removed = YEAR_CODES[years:course["years"]]
        marks = ",".join("?" * len(removed))
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM notes WHERE course = ? AND year IN (" + marks + ")",
            [code] + removed
        ).fetchone()["n"]
        if total:
            conn.close()
            return {"error": code + " still has " + str(total) + " note(s) in " + ", ".join(removed) +
                    ". Delete those notes first, or keep " + str(course["years"]) + " years."}, 400

    conn.execute("UPDATE courses SET name = ?, years = ? WHERE code = ?", (name, years, code))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# Delete a course together with its notes and uploaded files
@app.route("/api/courses/<code>", methods=["DELETE"])
def delete_course(code):
    if not is_admin():
        return {"error": "Admin only"}, 403

    code = code.upper()
    conn = get_db()
    if not conn.execute("SELECT 1 FROM courses WHERE code = ?", (code,)).fetchone():
        conn.close()
        return {"error": "Course not found."}, 404

    # remove the uploaded files of this course's notes
    for row in conn.execute("SELECT filename FROM notes WHERE course = ?", (code,)).fetchall():
        delete_upload(row["filename"])

    conn.execute("DELETE FROM notes WHERE course = ?", (code,))
    conn.execute("DELETE FROM courses WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# Send all notes to JavaScript
@app.route("/api/notes")
def get_notes():
    # /api/notes?course=BCA returns only the notes of that course
    course = request.args.get("course", "").upper()

    conn = get_db()
    if course:
        rows = conn.execute("SELECT * FROM notes WHERE course = ? ORDER BY id DESC", (course,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()   # newest first
    conn.close()

    notes = []
    for row in rows:
        note = dict(row)
        if row["filename"]:
            note["file_url"] = file_url(row["filename"])
        else:
            note["file_url"] = ""
        notes.append(note)
    return jsonify(notes)


# Save a new note from the form (admin only)
@app.route("/api/notes", methods=["POST"])
def add_note():
    if not session.get("is_admin"):
        return {"error": "Admin only"}, 403

    title = request.form["title"]
    course = request.form.get("course", "").upper()
    year = request.form["year"]

    # The course must exist and the year must belong to that course
    courses = get_courses()
    if course not in courses:
        return {"error": "Please choose a valid course."}, 400
    if year not in [y["code"] for y in years_for(courses[course]["years"])]:
        return {"error": course + " does not have " + year + "."}, 400

    subject = request.form["subject"]
    unit = request.form["unit"]
    description = request.form["description"]

    # Save the file if the admin chose one
    filename = ""
    file = request.files.get("file")
    if file and file.filename != "":
        filename = str(int(time.time())) + "_" + secure_filename(file.filename)
        try:
            save_upload(filename, file.read(), file.mimetype)
        except Exception:
            return {"error": "Could not upload the file. Please try again."}, 500

    conn = get_db()
    conn.execute(
        "INSERT INTO notes (title, course, year, subject, unit, description, filename, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, course, year, subject, unit, description, filename, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# Delete a note using its id (admin only)
@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    if not session.get("is_admin"):
        return {"error": "Admin only"}, 403

    conn = get_db()
    row = conn.execute("SELECT filename FROM notes WHERE id = ?", (note_id,)).fetchone()
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
    if row:
        delete_upload(row["filename"])
    return jsonify(ok=True)


# ---------- Manage admins (admin only) ----------

# Checks a username and password sent from the form. Returns an error text or None.
def check_admin_fields(username, password, need_username=True):
    if need_username and not re.fullmatch(r"[a-z0-9._-]{3,30}", username):
        return "Username must be 3 to 30 letters, numbers, dots, dashes or underscores."
    if len(password) < 6 or len(password) > 100:
        return "Password must be 6 to 100 characters."
    return None


# The page with the list of admins and Add / Change password / Delete buttons
@app.route("/admins")
def admins():
    if not is_admin():
        return redirect("/login")

    conn = get_db()
    rows = conn.execute("SELECT username, created_at, is_owner FROM admins "
                        "ORDER BY is_owner DESC, created_at, username").fetchall()
    conn.close()
    return render_template("admins.html", admins=rows, me=session.get("admin_user"),
                           owner=is_owner(), is_admin=True)


# Add an admin (for example a teacher)
@app.route("/api/admins", methods=["POST"])
def add_admin():
    if not is_owner():
        return {"error": "Only the owner can add admins."}, 403

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))

    error = check_admin_fields(username, password)
    if error:
        return {"error": error}, 400

    conn = get_db()
    if conn.execute("SELECT 1 FROM admins WHERE username = ?", (username,)).fetchone():
        conn.close()
        return {"error": username + " already exists."}, 409

    conn.execute("INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
                 (username, generate_password_hash(password), datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# Change the password of an admin
@app.route("/api/admins/<username>", methods=["PUT"])
def change_admin_password(username):
    if not is_admin():
        return {"error": "Admin only"}, 403

    username = username.lower()
    if not can_edit_admin(username):
        return {"error": "Only the owner can change another admin's password."}, 403
    password = str((request.get_json(silent=True) or {}).get("password", ""))
    error = check_admin_fields(username, password, need_username=False)
    if error:
        return {"error": error}, 400

    conn = get_db()
    cursor = conn.execute("UPDATE admins SET password_hash = ? WHERE username = ?",
                          (generate_password_hash(password), username))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return {"error": "Admin not found."}, 404
    return jsonify(ok=True)


# Rename an admin (the password stays the same)
@app.route("/api/admins/<username>/rename", methods=["PUT"])
def rename_admin(username):
    if not is_admin():
        return {"error": "Admin only"}, 403

    old = username.lower()
    if not can_edit_admin(old):
        return {"error": "Only the owner can rename another admin."}, 403
    new = str((request.get_json(silent=True) or {}).get("username", "")).strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,30}", new):
        return {"error": "Username must be 3 to 30 letters, numbers, dots, dashes or underscores."}, 400

    conn = get_db()
    if not conn.execute("SELECT 1 FROM admins WHERE username = ?", (old,)).fetchone():
        conn.close()
        return {"error": "Admin not found."}, 404
    if new != old and conn.execute("SELECT 1 FROM admins WHERE username = ?", (new,)).fetchone():
        conn.close()
        return {"error": new + " already exists."}, 409

    conn.execute("UPDATE admins SET username = ? WHERE username = ?", (new, old))
    conn.commit()
    conn.close()

    # if you renamed yourself, keep yourself logged in under the new name
    if session.get("admin_user") == old:
        session["admin_user"] = new
    return jsonify(ok=True)


# Delete an admin. You cannot delete yourself, so the site always keeps an admin.
@app.route("/api/admins/<username>", methods=["DELETE"])
def delete_admin(username):
    if not is_owner():
        return {"error": "Only the owner can delete admins."}, 403

    username = username.lower()
    if username == session.get("admin_user"):
        return {"error": "You cannot delete the account you are logged in with."}, 400

    conn = get_db()
    conn.execute("DELETE FROM admins WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# Lockout recovery. If you forget every admin password, run this in the project folder:
#     python app.py reset-admin <username> <new-password>
# It creates the admin, or sets a new password if the admin already exists,
# and makes that admin the owner.
# To see which admins exist and which database file is used:
#     python app.py list-admins
def reset_admin(username, password):
    username = username.strip().lower()
    error = check_admin_fields(username, password)
    if error:
        sys.exit("NOT SAVED: " + error)
    conn = get_db()
    conn.execute(
        "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash",
        (username, generate_password_hash(password), datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    # the account you reset becomes the one and only owner
    conn.execute("UPDATE admins SET is_owner = CASE WHEN username = ? THEN 1 ELSE 0 END", (username,))
    conn.commit()
    conn.close()
    print("Done. Admin '" + username + "' is ready.")
    list_admins()


def list_admins():
    conn = get_db()
    rows = conn.execute("SELECT username, is_owner FROM admins ORDER BY username").fetchall()
    conn.close()
    print("Database:", "the online database (DATABASE_URL)" if DATABASE_URL else os.path.join(app.root_path, "notes.db"))
    print("Admins  :", ", ".join(r["username"] + (" (owner)" if r["is_owner"] else "") for r in rows))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset-admin":
        if len(sys.argv) != 4:
            sys.exit('Usage: python app.py reset-admin <username> "<password>"  (put the password in quotes)')
        reset_admin(sys.argv[2], sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "list-admins":
        list_admins()
    else:
        # use_reloader=False avoids a leftover second process on Windows.
        # Use host="0.0.0.0" and debug=False if you want to open it from your phone.
        app.run(debug=True, use_reloader=False, host="127.0.0.1", port=5050)
