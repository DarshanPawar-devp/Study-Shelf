# Put Study-Shelf online with Vercel + Supabase

Vercel runs the website. Supabase keeps the data (the database and the uploaded files).
Both have a free plan. The dashboards change their menus now and then, so if a button
has a slightly different name, look for the closest one.

Running on your own computer still works exactly as before (`python app.py`):
without the settings below, the app uses `notes.db` and the uploads folder.

---

## Part 1: Supabase (database + file storage)

1. Go to supabase.com, sign in and click **New project**.
   Choose a name, a region close to you, and a **database password**.
   Use only letters and numbers in that password, and save it somewhere.
2. Open **Storage**, click **New bucket**, name it `notes`, and turn on **Public bucket**.
3. Collect three values:
   - **SUPABASE_URL**: Project Settings, then API (or Data API). Copy the **Project URL**,
     for example `https://abcdwxyz.supabase.co`.
   - **SUPABASE_SERVICE_KEY**: on the API keys page, copy the **service_role** (secret) key.
     This key can do anything, so never put it in GitHub or show it to anyone.
   - **DATABASE_URL**: click **Connect** at the top of the project, choose
     **Transaction pooler**, and copy the connection string. Replace `[YOUR-PASSWORD]`
     with your database password. It looks like:
     `postgresql://postgres.abcdwxyz:YOURPASSWORD@aws-0-xx.pooler.supabase.com:6543/postgres`

## Part 2: GitHub

Upload these project files to your repository (Add file, then Upload files):
`app.py`, `requirements.txt`, `migrate_to_supabase.py`, `DEPLOY_VERCEL.md`,
`.gitignore`, and the folders `templates` and `public`.

Then **delete the old `static` folder** from the repository. The css and js files now
live in `public/static`.

Do not upload `notes.db` or `public/static/uploads`.

## Part 3: Vercel

1. Go to vercel.com, sign in with GitHub, click **Add New, then Project**, and import
   your repository. Vercel detects Flask by itself. You do not need a build command.
2. Before clicking Deploy, open **Environment Variables** and add:

   | Name | Value |
   |---|---|
   | `SECRET_KEY` | a long random text (see below) |
   | `ADMIN_USER` | the owner username you want, for example `noteshub` |
   | `ADMIN_PASS` | the owner password (at least 6 characters) |
   | `DATABASE_URL` | the Transaction pooler string from Part 1 |
   | `SUPABASE_URL` | the Project URL from Part 1 |
   | `SUPABASE_SERVICE_KEY` | the service_role key from Part 1 |
   | `SUPABASE_BUCKET` | `notes` |

   To make a SECRET_KEY, run this on your computer and copy the result:
   `python -c "import secrets; print(secrets.token_hex(32))"`

3. Click **Deploy**. When it finishes, open the link Vercel gives you and log in as admin.

`ADMIN_USER` and `ADMIN_PASS` are only used on the very first start, to create the owner.
After that, manage admins from the website (Manage admins). If you change an environment
variable later, redeploy so the change takes effect.

## Part 4: Move your existing notes online (optional)

If you already have notes on your computer that you want online, run this once on your
computer, in the project folder next to your `notes.db`:

```powershell
$env:DATABASE_URL="paste-the-transaction-pooler-string"
$env:SUPABASE_URL="https://abcdwxyz.supabase.co"
$env:SUPABASE_SERVICE_KEY="paste-the-service-role-key"
$env:SUPABASE_BUCKET="notes"
python migrate_to_supabase.py
```

It asks you to type YES, because it REPLACES the courses, notes and admins online with
the ones from your computer (including your admin logins). It also uploads the files
from your uploads folder.

If you get locked out online, run the same four `$env:` lines and then:
`python app.py reset-admin yourname "new-password"`

## Things to know

- **Upload limit: 4 MB per file online.** Vercel does not accept bigger requests.
  On your own computer there is no limit.
- The first visit after a quiet period can take a few seconds to load.
- Uploaded files are public to anyone who has the link to the file. Students need that
  to download them, but do not upload private documents.
- Local files moved: the uploads folder is now `public/static/uploads`. If you run the app
  on your computer, copy your old `static/uploads` files there.
