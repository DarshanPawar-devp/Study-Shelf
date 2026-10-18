# StudyShelf - student features (setup, testing, explanation)

## What was added
| Feature | Where |
|---|---|
| Student register / login / logout / password reset (Supabase Auth) | `students.py`, `templates/student_auth.html`, `static/auth.js` |
| Student dashboard + change course/year | `/dashboard` |
| Notification bell, badge, dropdown, mark all read, toast | `templates/_header.html`, `static/student.js`, `static/student.css` |
| Notifications page | `/notifications` |
| "Uploaded by" on every note | `app.py` (`/api/notes`), `static/app.js` |
| Admin display names ("Faculty 1") | Manage admins > Display name |
| Admin student list (search, course filter, sort, pages) | `/students` |
| Admin analytics (cards + 4 charts, 7/30 days) | `/analytics` |
| SQL migration + rollback | `migrations/001_student_features.sql`, `001_rollback.sql` |

My Downloads was removed from the plan, so nothing tracks downloads.
Admin login, notes, uploads, downloads, courses and Manage admins work as before.

## Files
New: `students.py`, `templates/{student_auth,dashboard,notifications,students,analytics}.html`,
`static/{student.js,auth.js,analytics.js,student.css}`, `migrations/*`, this file.
Changed: `app.py` (4 small patches + registers `students.py`), `templates/{_header,_fonts,role,courses,admins}.html`,
`static/{app.js,admins.js}`.
Not changed: `requirements.txt`, `migrate_to_supabase.py`, `login.html`, `manage.html`, `index.html`, `style.css`.

## Setup order (do it in this order)
1. **Supabase > SQL Editor**: paste `migrations/001_student_features.sql`, Run. (Old code keeps working after this step.)
2. **Supabase > Authentication > Providers > Email**: decide "Confirm email".
   ON = students must click an emailed link before logging in (free plan limits how many emails Supabase sends per hour).
   OFF = easier for a demo. Either works.
3. **Supabase > Authentication > URL Configuration**: set *Site URL* to `https://study-shelf-gamma.vercel.app`
   and add `https://study-shelf-gamma.vercel.app/student/reset` to *Redirect URLs* (needed for password reset).
4. **Vercel > Settings > Environment Variables**: add `SUPABASE_ANON_KEY` = the public "anon / publishable" key
   (Supabase > Project Settings > API Keys). It is a public key, not a secret. Optional: `SITE_URL` = your site address.
   The existing variables stay. NEVER put the service_role key anywhere except Vercel's variables.
5. **GitHub**: upload the new/changed files (Add file > Upload files, keep the folder names).
   Do not upload `notes.db`. Vercel redeploys by itself.
6. Open the site. If the student buttons do not appear, a variable or the migration is missing (the site then behaves exactly as before).

Local run: `python app.py` still works without any of this (admin features only). Student features need `DATABASE_URL`,
`SUPABASE_URL`, `SUPABASE_ANON_KEY` set in your terminal.
WARNING: never run `migrate_to_supabase.py` against the live project again; it REPLACES notes, courses and admins.

## Manual test list
1. Admin login, add a note with a PDF, download it, edit it, delete a test note.
2. Register a BCA student (SY or all years). Log out, log in. Close the browser, reopen: still logged in (14 days).
3. Wrong password 5 times: login is blocked for 10 minutes (same idea as the admin login).
4. Register a second student in BBA. Admin uploads a BCA note: the BCA student gets a bell badge (and a toast within about a minute); the BBA student gets nothing.
5. Refresh the BCA student's page: the toast does not come back. Click the bell: note title, course, subject, date, Unread. Click it: the note opens highlighted. Badge drops. "Mark all as read" sets the badge to 0.
6. Log out as the student, upload another BCA note as admin, log in again: it is in the panel (offline case).
7. Student opens `/students`, `/analytics`, `/api/analytics`: redirected / refused. Admin can open them.
8. Admin > Manage admins > Display name: set "Faculty 1", upload a note: card shows "Uploaded by: Faculty 1". Old notes show "Uploader unknown".
9. Forgot password: email link opens `/student/reset`, set a new password, log in with it.
10. Phone-width check of the bell panel, dashboard, student table (scrolls sideways) and charts.

## Database changes (migration 001), in plain words
- `admins.id`: a permanent number per admin (usernames can be renamed). `admins.display_name`: optional friendly name.
- `notes.uploaded_by`: the admin id of the uploader. Old notes stay empty = "Uploader unknown".
- `profiles`: one row per student (name, course, year, created, last active). Linked to Supabase Auth by id. No passwords or roles here, so a student has no field to edit to become an admin.
- `notifications`: (student, note, read time). UNIQUE(student, note) = no duplicates.
- `login_events`: one row per successful student password login.
- RLS is ON for the three new tables; students can only READ their own rows via Supabase's own API. Writes happen only in Flask.

## How it works (beginner version)
- **Authentication**: the student's email and password go to Supabase Auth (it stores the password safely). Flask then keeps its own signed login cookie with the student's id. Admins are completely separate (`admins` table, unchanged).
- **Authorization**: every sensitive route checks the session on the server (`student_required`, `admin_required`). Hiding a button is never the only protection. Queries use the id from the session, never an id sent by the browser.
- **RLS** = rules inside the database about which rows a user may see. Flask connects as the database owner, which skips RLS, so in this app the Flask checks are the main wall and RLS is a safety net for anything using Supabase's public API.
- **Notifications**: when an admin saves a note, Flask inserts one notification for every student whose course matches (and whose year is empty or matches). Admins are not in `profiles`, so they never receive one. The note is saved first; a failure while notifying cannot lose the note.
- **Toast**: the browser asks `/api/notifications` once a minute while the tab is visible and remembers the newest id it already showed (in localStorage), so refreshing does not repeat it. Dismissing only hides the toast.
- **Last active / active now**: updated at most once a minute per student. "Active now" = activity in the last 5 minutes. It is based on requests, not proof of someone watching the screen.
- **Uploader**: stored as an admin id at upload time (from the admin's session) and turned into a name by a database join. The browser never sends a name. Editing a note does not change the uploader.
- **Analytics**: SQL counts on `profiles` and `login_events`, grouped by UTC day. Charts are drawn by Chart.js (loaded from cdnjs).

## Unfinished work, assumptions, limits (please read)
- **Not tested against your real Supabase.** I could test the old features, access guards and page rendering locally; I could NOT run the new SQL, Supabase Auth calls, emails, realtime behaviour or charts against a live project. Expect to fix small things when you first run it.
- The student list reads email and verification state from `auth.users`; this assumes your database connection can read that table (normally true for the `postgres` user).
- "Students who logged in per day" is the daily-active definition used: distinct students with a login that day. Real browsing activity is not stored per day. History before tracking started does not exist and shows 0; the page says so.
- The toast watermark lives in each browser: a new browser or cleared storage shows notifications in the panel but no pop-up.
- Account status is limited to Verified / Email not confirmed / Suspended (from Supabase). There is no ban button yet.
- Year (not semester) is what exists in your data, so matching is course + optional year.
- No CAPTCHA on registration; Supabase has its own rate limits. Admin JSON routes rely on SameSite=Lax cookies (no CSRF tokens). Files in the bucket remain public by link (as before).
- Students pick their course themselves; there is no admin approval.
- The old `login_attempts` table is reused for student lock-out (keys start with `student:`).

## Interview summary
"StudyShelf is a Flask and Supabase notes-sharing site I extended with student accounts. Students register through Supabase Auth and choose a course. When an admin uploads a note, the server creates one notification per matching student, protected by a unique constraint, and the student sees a bell badge and a toast without refreshing. Notes show the uploader from a trusted admin record. Admins get a student list and an analytics dashboard built from real login and registration records. Access control is enforced on the server and with row level security, and the existing admin system was left untouched."
