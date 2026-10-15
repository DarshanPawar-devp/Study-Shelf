# Study-Shelf

A simple web app for sharing study notes. An admin uploads notes, and students can browse and download them, organised by year, subject and unit.

## Features

- Browse all uploaded notes, newest first
- Each note has a title, year, subject, unit, description and an optional file attachment
- Admin login to add and delete notes
- Notes and files are stored locally (SQLite database and an uploads folder)
- Works on a phone over the same Wi-Fi network

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript

## Project Structure

```
Study-Shelf/
├── app.py              # Flask app and API routes
├── requirements.txt    # Python dependencies
├── static/
│   ├── app.js
│   ├── style.css
│   └── login.css
└── templates/
    ├── index.html      # Home page
    └── login.html      # Admin login page
```

## How to Run

1. Install Python 3 from python.org.
2. Download or clone this repository.
3. Open a terminal in the project folder and install the dependencies:
```
   pip install -r requirements.txt
```
4. Start the app:
```
   python app.py
```
5. Open http://localhost:5050 in your browser.

The database (`notes.db`) and the `static/uploads/` folder are created automatically on first run.

## Admin Access

Go to `/login` and sign in with the admin account set in `app.py`. Change the default credentials before using the app anywhere other than your own computer.

## Team

- [darshan pawar]
- [Teammate Name]

Guided by: [Professor / Guide Name], [College Name]

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
