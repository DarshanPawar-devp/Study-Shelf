/* ==========================================================
   StudyShelf - app.js
   Job of this file:
   1. Get notes from the Flask backend (API)
   2. Show them as cards
   3. Filter by year, subject and search text
   4. Add a new note (with optional file) - ADMIN ONLY
   5. Delete a note - ADMIN ONLY
   ========================================================== */


/* ---------- 1. SELECT HTML ELEMENTS ----------
   getElementById finds an element using the id written in index.html.
   We store each one in a variable so we can use it later. */
const yearSelect = document.getElementById("year");
const subjectSelect = document.getElementById("subject");
const searchInput = document.getElementById("search");
const notesBox = document.getElementById("notes");
const countText = document.getElementById("count");

// Year picker (first screen) and the notes area (second screen)
const yearPicker = document.getElementById("yearPicker");
const notesView = document.getElementById("notesView");
const changeYearBtn = document.getElementById("changeYear");

// These 5 elements exist ONLY when the admin is logged in.
// For normal visitors they are null (not on the page).
const addButton = document.getElementById("addNoteBtn");   // FIXED: id is addNoteBtn in index.html
const closeButton = document.getElementById("closeButton");
const modal = document.getElementById("modal");            // the <dialog> popup
const noteForm = document.getElementById("noteForm");
const messageText = document.getElementById("message");    // error/success text

// true only when the admin is logged in
const isAdmin = document.body.dataset.admin === "yes";

// The course of this page (BCA, BBA, ...). It is written into <body data-course="..."> by Flask.
const course = document.body.dataset.course;


/* ---------- 2. APP DATA ----------
   allNotes keeps every note received from Flask.
   Filtering happens on this array, so we don't call the server
   again every time the user types or changes a dropdown. */
let allNotes = [];


/* ---------- 3. HELPER: ESCAPE HTML ----------
   User-typed text is placed inside HTML (innerHTML).
   If someone types <script>..., it could run as code (XSS attack).
   This function turns special characters into safe text. */
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";   // textContent treats everything as plain text
    return div.innerHTML;           // returns the safe version
}


/* ---------- ICONS ----------
   Small line icons written as SVG text, so we need no extra files. */
const ICON_FILE = '<svg class="ico" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>';
const ICON_DOWNLOAD = '<svg class="ico" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';


/* ---------- HELPER: SHOW THE DATE LIKE "9:30 AM", "Yesterday", "May 20" ---------- */
function formatDate(text) {
    if (!text) return "";                       // old notes have no date
    const date = new Date(text);
    if (isNaN(date)) return "";

    const now = new Date();
    const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const days = Math.round((startOfDay(now) - startOfDay(date)) / 86400000);

    if (days === 0) return date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
    if (days === 1) return "Yesterday";

    const options = { month: "short", day: "numeric" };
    if (date.getFullYear() !== now.getFullYear()) options.year = "numeric";
    return date.toLocaleDateString("en-US", options);
}


/* ---------- HELPER: CLEAN FILE NAME ----------
   Flask saves files as "1759999999_Python.pdf" (time + name).
   For downloading we remove the time so the user gets "Python.pdf". */
function getFileName(url) {
    const name = decodeURIComponent(url.split("/").pop());
    return name.replace(/^\d+_/, "");
}


/* ---------- 4. LOAD NOTES FROM FLASK ----------
   async/await lets us wait for the server without freezing the page.
   fetch("/api/notes") sends a GET request to Flask. */
async function loadNotes() {
    try {
        // ask Flask only for the notes of this course
        const response = await fetch("/api/notes?course=" + encodeURIComponent(course));
        allNotes = await response.json();   // convert JSON text -> JS array

        fillSubjects();   // build the subject dropdown from the data
        showNotes();      // draw the cards
    } catch (error) {
        notesBox.innerHTML =
            '<div class="empty">Could not load notes. Is the Flask server running?</div>';
    }
}


/* ---------- 5. FILL THE SUBJECT DROPDOWN ----------
   The HTML only has "All Subjects". We add the real subjects
   from the notes. Set removes duplicates. */
function fillSubjects() {
    const selected = subjectSelect.value;   // remember what the user chose

    // Only list subjects of the chosen year (or every subject when "All Years")
    const year = yearSelect.value;
    const notesOfYear = year === "all" ? allNotes : allNotes.filter(note => note.year === year);
    const subjects = [...new Set(notesOfYear.map(note => note.subject))].sort();

    subjectSelect.innerHTML = '<option value="all">All Subjects</option>' +
        subjects.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");

    // put the previous choice back if it still exists
    subjectSelect.value = subjects.includes(selected) ? selected : "all";
}


/* ---------- 6. FILTER + SHOW NOTE CARDS ---------- */
function showNotes() {
    const year = yearSelect.value;
    const subject = subjectSelect.value;
    const search = searchInput.value.trim().toLowerCase();

    // filter() keeps only notes that pass ALL three conditions
    const filtered = allNotes.filter(note => {
        const matchYear = year === "all" || note.year === year;
        const matchSubject = subject === "all" || note.subject === subject;

        // search in title + unit + subject + description together
        const text = `${note.title} ${note.unit} ${note.subject} ${note.description || ""}`.toLowerCase();
        const matchSearch = text.includes(search);

        return matchYear && matchSubject && matchSearch;
    });

    // update "6 resources found" text
    countText.textContent =
        `${filtered.length} resource${filtered.length === 1 ? "" : "s"} found`;

    // nothing matched -> show the empty message (uses the .empty CSS class)
    if (filtered.length === 0) {
        notesBox.innerHTML = '<div class="empty">No notes found. Try another filter or add a note.</div>';
        return;
    }

    // map() turns each note into one list row, join() combines them into one string
    notesBox.innerHTML = filtered.map(note => {
        // second line: "Subject · Unit — description"
        const info = [note.subject, note.unit].filter(Boolean).join(" · ");
        const details = note.description ? info + " \u2014 " + note.description : info;

        const hasFile = Boolean(note.file_url);

        // items inside the 3-dots menu (Delete is added ONLY for the admin)
        let menuItems = "";
        if (hasFile) {
            menuItems += `<a href="${escapeHtml(note.file_url)}" target="_blank">Open file</a>`;
        }
        if (isAdmin) {
            menuItems += `<button class="delete" data-id="${note.id}">Delete</button>`;
        }

        return `
        <article class="note-row year-${escapeHtml(note.year)}">
            <div class="note-icon">${ICON_FILE}</div>

            <div class="note-main">
                <h3 title="${escapeHtml(note.title)}">${escapeHtml(note.title)}</h3>
                <p>${escapeHtml(details)}</p>
            </div>

            <div class="note-meta">
                <span class="tag">${escapeHtml(note.year)} \u00b7 ${escapeHtml(note.subject)}</span>
                <span class="note-date">${escapeHtml(formatDate(note.created_at))}</span>
                ${hasFile
                ? `<a class="icon-btn" title="Download" href="${escapeHtml(note.file_url)}" download="${escapeHtml(getFileName(note.file_url))}">${ICON_DOWNLOAD}</a>`
                : ""}
                ${menuItems
                ? `<details class="menu"><summary class="icon-btn" title="More">&#8942;</summary><div class="menu-list">${menuItems}</div></details>`
                : ""}
            </div>
        </article>`;
    }).join("");
}


/* ---------- 7. FILTER EVENTS ----------
   Re-draw the cards whenever the user changes something. */
yearSelect.addEventListener("change", showNotes);
subjectSelect.addEventListener("change", showNotes);
searchInput.addEventListener("input", showNotes);   // "input" fires on every keystroke


/* ---------- 7B. YEAR PICKER ----------
   The page first asks "Which year?". The year cards are made by Flask,
   so a 3-year course shows 3 cards and a 5-year course shows 5.
   When a year card is clicked we:
   1. set the year dropdown to that year (FY, SY, TY, 4Y, 5Y or all)
   2. hide the picker and show the notes */
document.querySelectorAll(".year-card").forEach(card => {
    card.addEventListener("click", () => {
        yearSelect.value = card.dataset.year;   // data-year="FY" in the HTML

        // Show the chosen year on the back button, e.g. "← Change year (TY)"
        if (changeYearBtn) {
            const label = card.dataset.year === "all" ? "All Years" : card.dataset.year;
            changeYearBtn.textContent = "\u2190 Change year (" + label + ")";
        }
        yearPicker.hidden = true;
        notesView.hidden = false;
        fillSubjects();   // refresh the subject list for this year
        showNotes();
    });
});

// "Change year" button goes back to the picker
if (changeYearBtn) {
    changeYearBtn.addEventListener("click", () => {
        notesView.hidden = true;
        yearPicker.hidden = false;
    });
}


/* ---------- 8. ADMIN ONLY: ADD NOTE POPUP + SAVE ----------
   Everything inside this "if" runs only for the admin.
   Visitors do not have the popup on their page, so we skip it.
   (This also stops the "cannot read null" error for visitors.) */
// Helps debugging: press F12 > Console to see this line
console.log("StudyShelf loaded. Admin:", isAdmin, "| Add Note button found:", !!addButton, "| popup found:", !!modal);

if (isAdmin && addButton && modal) {

    // Open the popup
    addButton.addEventListener("click", () => {
        messageText.textContent = "";   // clear old messages

        // If a year is already chosen, start the form on that year
        if (yearSelect.value !== "all") {
            noteForm.elements["year"].value = yearSelect.value;
        }
        if (typeof modal.showModal === "function") {
            modal.showModal();          // built-in <dialog> method
        } else {
            modal.setAttribute("open", "");   // fallback for old browsers
        }
    });

    // Close the popup (FIXED: this line was written twice before)
    closeButton.addEventListener("click", () => modal.close());

    // Save a new note
    // FormData collects every input (including the file) from the form.
    // fetch() sends it to Flask using POST.
    noteForm.addEventListener("submit", async (event) => {
        event.preventDefault();   // stop the browser's default page reload

        messageText.textContent = "Saving...";

        try {
            const response = await fetch("/api/notes", {
                method: "POST",
                body: new FormData(noteForm)
            });

            if (response.ok) {
                noteForm.reset();   // clear the form
                modal.close();      // close popup
                loadNotes();        // reload so the new card appears
            } else {
                const data = await response.json().catch(() => ({}));
                messageText.textContent = data.error || "Could not save the note.";
            }
        } catch (error) {
            messageText.textContent = "Server error. Please try again.";
        }
    });
}


/* ---------- CLOSE THE 3-DOTS MENU ----------
   Clicking anywhere outside an open menu closes it. */
document.addEventListener("click", (event) => {
    document.querySelectorAll(".menu[open]").forEach(menu => {
        if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
});


/* ---------- 9. DELETE A NOTE (ADMIN ONLY) ----------
   Cards are created dynamically, so we listen on the parent (notesBox)
   and check which child was clicked. This is called EVENT DELEGATION.
   Visitors have no Delete buttons, so this never runs for them. */
notesBox.addEventListener("click", async (event) => {
    const button = event.target.closest(".delete");
    if (!button) return;   // click was not on a delete button

    if (!confirm("Delete this note?")) return;

    // data-id="5" in the HTML is read here as button.dataset.id
    const response = await fetch(`/api/notes/${button.dataset.id}`, { method: "DELETE" });

    if (response.ok) {
        loadNotes();   // reload the cards
    } else {
        alert("Could not delete. Please log in as admin again.");   // e.g. the session ended
    }
});


/* ---------- 10. START THE APP ----------
   Runs once when the page opens. */
loadNotes();