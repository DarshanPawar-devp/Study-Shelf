import os
import time
from datetime import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "any-long-random-text-here"   # needed to remember who is logged in
app.config["TEMPLATES_AUTO_RELOAD"] = True   # picks up index.html edits without restarting
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0   # browser always loads the newest app.js / style.css

# ---------- Admin account ----------
# To change the admin login, edit these two lines and restart the app.
ADMIN_USER = "noteshub@.com"
ADMIN_PASS = "admin12"

# The password is hashed in memory when the app starts
ADMIN_HASH = generate_password_hash(ADMIN_PASS)


# ---------- Cache busting ----------
# Adds ?v=<last-changed-time> to every static link so the browser
# downloads the new file as soon as it changes.
def dated_url_for(endpoint, **values):
    if endpoint == "static" and values.get("filename"):
        file_path = os.path.join(app.root_path, "static", values["filename"])
        if os.path.isfile(file_path):
            values["v"] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)


@app.context_processor
def use_dated_url_for():
    return dict(url_for=dated_url_for)


UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Connect to the database file.
# The notes table is created here if it is missing, so deleting notes.db
# can never break the app: a fresh empty database is made automatically.
def get_db():
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

    # Older databases have no date column yet, so add it once
    columns = [row[1] for row in conn.execute("PRAGMA table_info(notes)").fetchall()]
    if "created_at" not in columns:
        conn.execute("ALTER TABLE notes ADD COLUMN created_at TEXT")

    conn.commit()
    return conn


# Home page
@app.route("/")
def home():
    return render_template("index.html", is_admin=session.get("is_admin", False))


# Show the login page (GET) and check the details (POST)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USER and check_password_hash(ADMIN_HASH, password):
            session["is_admin"] = True        # remember that the admin is logged in
            return redirect("/")
        else:
            return redirect("/login?error=1") # wrong details, show the error

    return render_template("login.html")


# Log out by clearing the memory
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# Send all notes to JavaScript
@app.route("/api/notes")
def get_notes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()   # newest first
    conn.close()

    notes = []
    for row in rows:
        note = dict(row)
        if row["filename"]:
            note["file_url"] = "/static/uploads/" + row["filename"]
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
    year = request.form["year"]
    subject = request.form["subject"]
    unit = request.form["unit"]
    description = request.form["description"]

    # Save the file if the admin chose one
    filename = ""
    file = request.files.get("file")
    if file and file.filename != "":
        filename = str(int(time.time())) + "_" + secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    conn = get_db()
    conn.execute(
        "INSERT INTO notes (title, year, subject, unit, description, filename, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, year, subject, unit, description, filename, datetime.now().isoformat(timespec="seconds"))
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
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

if __name__ == "__main__":
       app.run(debug=False, host="0.0.0.0", port=5050)  # reachable from your phone