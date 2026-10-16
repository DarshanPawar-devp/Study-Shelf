# Study-Shelf

A simple web app for sharing study notes. An admin uploads notes, and students can browse and download them, organised by course, year, subject and unit.

## Features

* Students pick a course and year, then browse and download notes (newest first)
* Each note has a title, year, subject, unit, description and an optional file attachment
* Admin login to add and delete notes
* Admins can add, edit and delete courses from the website (Manage courses)
* Multiple admin accounts, each with their own login (Manage admins)
* Notes and files are stored locally (SQLite database and an uploads folder)

## Tech Stack

* Backend: Python, Flask
* Database: SQLite
* Frontend: HTML, CSS, JavaScript

## Project Structure

```
Study-Shelf/
├── app.py              # Flask app and API routes
├── requirements.txt    # Python dependencies
├── static/
│   ├── app.js
│   ├── manage.js       # Manage courses page
│   ├── admins.js       # Manage admins page
│   ├── style.css
│   └── login.css
└── templates/
    ├── _header.html    # Header shared by every page
    ├── role.html       # First page: Student or Admin
    ├── courses.html    # Choose a course
    ├── index.html      # Notes page
    ├── login.html      # Admin login page
    ├── manage.html     # Manage courses (admin)
    └── admins.html     # Manage admins (admin)
```

## How to Run

1. Install Python 3 from python.org.
2. Download or clone this repository.
3. Open a terminal in the project folder and install the dependencies:

```
   pip install -r requirements.txt
```

4. Set the first admin login (only needed the very first time, see Admin Access below) and start the app:

```
   $env:ADMIN_USER="youradmin"
   $env:ADMIN_PASS="your-password"
   python app.py
```

5. Open http://localhost:5050 in your browser.

The database (`notes.db`) and the `static/uploads/` folder are created automatically on first run.

To open the site from your phone on the same Wi-Fi, change the last line of `app.py` to use `host="0.0.0.0"` and `debug=False`.

## Admin Access

Admins are stored in the database, and each admin has their own login.

**First run:** the first time the app starts, `ADMIN_USER` and `ADMIN_PASS` create the first admin, who becomes the **owner**. After that those variables are ignored. Log in at `/login` and open **Manage admins** to add teachers, rename accounts or change passwords.

| | Owner | Other admins |
|---|---|---|
| Add or delete admins | Yes | No |
| Change other admins' passwords or usernames | Yes | No |
| Change their own password or username | Yes | Yes |
| Manage courses and notes | Yes | Yes |

**Locked out?** Run this in the project folder. It sets the password and makes that account the owner:

```
python app.py reset-admin youradmin "new-password"
```

To see which admins exist: `python app.py list-admins`

## Before Deploying

* Set a strong `SECRET_KEY` environment variable.
* Turn off `debug=True` at the bottom of `app.py`.
* `notes.db` and `static/uploads/` are not stored in the repository. A new database is created on first run.

## Team

* [darshan pawar]
* [Teammate Name]

Guided by: [Professor / Guide Name], [College Name]

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/DarshanPawar-devp/Study-Shelf/blob/main/LICENSE) file for details.
