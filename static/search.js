/* ==========================================================
   StudyShelf - search.js
   Job of this file: the search bar on the "Choose a course" page.
   A visitor types words such as "bca ty python unit 1" and sees every
   matching note from ALL courses. Every word must match somewhere in the
   note's course, year, subject, unit or title.
   ========================================================== */

const searchBox = document.getElementById("globalSearch");

if (searchBox) {

    /* ---------- 1. DATA FROM FLASK ----------
       courses.html writes the course and year names into data-* attributes.
       JSON.parse turns that text back into JavaScript objects. */
    const courseInfo = JSON.parse(searchBox.dataset.courses);   // {"BCA": {"name": "...", "years": 3}, ...}
    const yearNames = JSON.parse(searchBox.dataset.years);      // {"FY": "First Year", ...}
    const courseCodes = Object.keys(courseInfo).map(code => code.toLowerCase());
    const yearCodes = Object.keys(yearNames).map(code => code.toLowerCase());

    const resultsBox = document.getElementById("searchResults");
    const listBox = document.getElementById("searchList");
    const countText = document.getElementById("searchCount");
    const hint = document.getElementById("searchHint");
    const courseGrid = document.getElementById("courseGrid");

    // All notes are downloaded once, the first time the visitor types. null = not loaded yet.
    let allNotes = null;

    /* ---------- 2. HELPERS ---------- */
    // Turns special characters into safe text, so a note title can never run as code (XSS)
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text ?? "";
        return div.innerHTML;
    }

    // "1759999999_Python.pdf" -> "Python.pdf"
    function getFileName(url) {
        return decodeURIComponent(url.split("/").pop()).replace(/^\d+_/, "");
    }

    const ICON_FILE = '<svg class="ico" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>';
    const ICON_DOWNLOAD = '<svg class="ico" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';

    /* ---------- 3. DOES A NOTE MATCH ONE TYPED WORD? ----------
       text      = course code + course name + year code + year name + subject + unit + title
       squashed  = the same text without spaces, so "unit1" finds "Unit 1" */
    function wordMatches(note, text, squashed, word) {
        // A word that is exactly a course code (bca) or a year code (ty) must match
        // that field exactly. Otherwise "mca" would also find IMCA, and "ty" would find "city".
        if (courseCodes.includes(word) || yearCodes.includes(word)) {
            return (note.course || "").toLowerCase() === word || (note.year || "").toLowerCase() === word;
        }
        return text.includes(word) || squashed.includes(word);
    }

    /* ---------- 4. SHOW THE RESULTS ---------- */
    function showResults(found) {
        countText.textContent = found.length + " note" + (found.length === 1 ? "" : "s") + " found";

        if (found.length === 0) {
            listBox.innerHTML = '<div class="empty">No notes found. Try fewer or different words.</div>';
            return;
        }

        listBox.innerHTML = found.map(note => {
            // second line, for example: "BCA · Third Year (TY) · Python Programming · Unit 1"
            const yearText = yearNames[note.year] ? yearNames[note.year] + " (" + note.year + ")" : note.year;
            const where = [note.course, yearText, note.subject, note.unit].filter(Boolean).join(" \u00b7 ");
            const hasFile = Boolean(note.file_url);

            return `
            <article class="note-row year-${escapeHtml(note.year)}">
                <div class="note-icon">${ICON_FILE}</div>
                <div class="note-main">
                    <h3 title="${escapeHtml(note.title)}">${escapeHtml(note.title)}</h3>
                    <p>${escapeHtml(where)}</p>
                </div>
                <div class="note-meta">
                    ${hasFile
                    ? `<a class="icon-btn" title="Download" href="${escapeHtml(note.file_url)}" download="${escapeHtml(getFileName(note.file_url))}">${ICON_DOWNLOAD}</a>`
                    : ""}
                    <a class="icon-btn" title="Open ${escapeHtml(note.course)} notes" href="/course/${encodeURIComponent(note.course)}">&rarr;</a>
                </div>
            </article>`;
        }).join("");
    }

    /* ---------- 5. RUN THE SEARCH ----------
       Runs on every keystroke. It always reads what is typed RIGHT NOW,
       so it never shows results for old text. */
    async function update() {
        const words = searchBox.value.trim().toLowerCase().split(/\s+/).filter(Boolean);

        // Nothing typed: hide the results and show the course cards again
        if (words.length === 0) {
            resultsBox.hidden = true;
            courseGrid.hidden = false;
            hint.hidden = false;
            return;
        }

        courseGrid.hidden = true;
        hint.hidden = true;
        resultsBox.hidden = false;

        // First search: download the notes once (later searches use the saved list)
        if (allNotes === null) {
            countText.textContent = "Loading...";
            try {
                const response = await fetch("/api/notes");
                if (!response.ok) throw new Error("bad response");
                allNotes = await response.json();
            } catch (error) {
                listBox.innerHTML = '<div class="empty">Could not load the notes. Please try again.</div>';
                countText.textContent = "";
                return;
            }
            return update();   // search again with whatever is typed now
        }

        // keep the notes where EVERY typed word matches
        const found = allNotes.filter(note => {
            const course = courseInfo[note.course] || { name: "" };
            const text = [note.course, course.name, note.year, yearNames[note.year], note.subject, note.unit, note.title]
                .join(" ").toLowerCase();
            const squashed = text.replace(/\s+/g, "");
            return words.every(word => wordMatches(note, text, squashed, word));
        });
        showResults(found);
    }

    searchBox.addEventListener("input", update);   // "input" fires on every keystroke
}
