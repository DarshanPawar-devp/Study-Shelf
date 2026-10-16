"""
Copies your LOCAL data (notes.db and the uploaded files) to Supabase.
Run it ONCE from your computer, before or after the first deploy.

    1. Set DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY (see DEPLOY_VERCEL.md)
    2. python migrate_to_supabase.py

WARNING: it REPLACES the courses, notes and admins in the online database.
"""
import mimetypes
import os
import sqlite3
import sys

here = os.path.dirname(os.path.abspath(__file__))

if not os.environ.get("DATABASE_URL"):
    sys.exit("Set DATABASE_URL first (see DEPLOY_VERCEL.md).")

import app as site

if not site.USE_SUPABASE:
    sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY first (see DEPLOY_VERCEL.md).")

local_path = os.path.join(here, "notes.db")
if not os.path.exists(local_path):
    sys.exit("notes.db was not found next to this file. Nothing to copy.")

if input("This REPLACES everything in the online database. Type YES to continue: ") != "YES":
    sys.exit("Cancelled.")

local = sqlite3.connect(local_path)
local.row_factory = sqlite3.Row
courses = local.execute("SELECT * FROM courses ORDER BY position, code").fetchall()
admins = local.execute("SELECT * FROM admins").fetchall()
notes = local.execute("SELECT * FROM notes ORDER BY id").fetchall()
note_columns = notes[0].keys() if notes else []

online = site.get_db()          # creates the tables if they are missing

# Start from empty tables, then copy everything
online.execute("DELETE FROM notes")
online.execute("DELETE FROM courses")
online.execute("DELETE FROM admins")

for c in courses:
    online.execute("INSERT INTO courses (code, name, years, position) VALUES (?, ?, ?, ?)",
                   (c["code"], c["name"], c["years"], c["position"]))

for a in admins:
    online.execute("INSERT INTO admins (username, password_hash, created_at, is_owner) VALUES (?, ?, ?, ?)",
                   (a["username"], a["password_hash"], a["created_at"], a["is_owner"]))

for n in notes:
    online.execute(
        "INSERT INTO notes (id, title, course, year, subject, unit, description, filename, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (n["id"], n["title"], n["course"] if "course" in note_columns else None, n["year"], n["subject"],
         n["unit"], n["description"], n["filename"], n["created_at"]))

# The next new note must get an id after the copied ones
online.execute("SELECT setval(pg_get_serial_sequence('notes', 'id'), (SELECT COALESCE(MAX(id), 1) FROM notes))")
online.commit()
online.close()
print("Copied", len(courses), "courses,", len(admins), "admins and", len(notes), "notes.")

# Copy the uploaded files (they may be in either folder, depending on your version)
folders = [os.path.join(here, "public", "static", "uploads"), os.path.join(here, "static", "uploads")]
copied = missing = 0
for n in notes:
    name = n["filename"]
    if not name:
        continue
    path = next((os.path.join(f, name) for f in folders if os.path.isfile(os.path.join(f, name))), None)
    if not path:
        print("  file not found, skipped:", name)
        missing += 1
        continue
    with open(path, "rb") as f:
        site.save_upload(name, f.read(), mimetypes.guess_type(name)[0] or "application/octet-stream")
    copied += 1
print("Uploaded", copied, "files to Supabase Storage.", ("%d missing." % missing) if missing else "")
print("Done. You can now open your online site.")
