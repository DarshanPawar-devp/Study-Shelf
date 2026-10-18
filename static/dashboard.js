/* ==========================================================
   StudyShelf - dashboard.js  (student dashboard only)
   Shows the notes of the student's own course right on the dashboard.
   It uses the same /api/notes?course=... address and the same file links as the course page,
   so nothing about uploading or downloading changes.
   ========================================================== */
(function () {
    const root = document.getElementById("dashNotes");
    if (!root) return;

    const course = root.dataset.course;
    const myYear = root.dataset.year;           // "" = the student follows all years
    const searchBox = document.getElementById("dnSearch");
    const subjectBox = document.getElementById("dnSubject");
    const yearBox = document.getElementById("dnYear");
    const countText = document.getElementById("dnCount");
    const list = document.getElementById("dnList");

    let notes = [];

    function esc(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function dateText(text) {
        if (!text) return "";
        const d = new Date(text);
        return isNaN(d) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    }

    // Same rule as the course page: remove the time prefix, so the download is "Python.pdf"
    function fileName(url) {
        return decodeURIComponent(url.split("/").pop()).replace(/^\d+_/, "");
    }

    function setBusy(busy) { list.setAttribute("aria-busy", String(busy)); }

    function showMessage(html) {
        setBusy(false);
        list.className = "";
        list.innerHTML = html;
    }

    /* ----- subject dropdown follows the chosen year ----- */
    function fillSubjects() {
        const keep = subjectBox.value;
        const year = yearBox.value;
        const pool = year === "all" ? notes : notes.filter(n => n.year === year);
        const subjects = [...new Set(pool.map(n => n.subject).filter(Boolean))].sort();
        subjectBox.innerHTML = '<option value="all">All subjects</option>' +
            subjects.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
        subjectBox.value = subjects.includes(keep) ? keep : "all";
    }

    function card(n) {
        const hasFile = Boolean(n.file_url);
        const openUrl = hasFile ? n.file_url : "/course/" + encodeURIComponent(n.course || course) + "?note=" + n.id;
        const when = dateText(n.created_at);
        return `
        <article class="ss-notecard" data-note-id="${n.id}">
            <div class="ss-notecard-top">
                ${n.year ? `<span class="ss-chip">${esc(n.year)}</span>` : "<span></span>"}
                ${when ? `<span class="ss-muted">${esc(when)}</span>` : ""}
            </div>
            <h3>${esc(n.title)}</h3>
            <p class="ss-notecard-sub">${esc([n.subject, n.course || course].filter(Boolean).join(" \u00b7 "))}</p>
            ${n.unit ? `<p class="ss-notecard-sub">${esc(n.unit)}</p>` : ""}
            <p class="ss-uploader">Uploaded by ${esc(n.uploader_name || "Uploader unknown")}</p>
            <div class="ss-notecard-actions">
                <a class="ss-btn ss-btn-sm" href="${esc(openUrl)}"${hasFile ? ' target="_blank" rel="noopener"' : ""}>${hasFile ? "Open" : "View details"}</a>
                ${hasFile ? `<a class="ss-btn ss-btn-sm ss-btn-light" href="${esc(n.file_url)}" download="${esc(fileName(n.file_url))}">Download</a>` : ""}
            </div>
        </article>`;
    }

    function render() {
        const year = yearBox.value;
        const subject = subjectBox.value;
        const q = searchBox.value.trim().toLowerCase();

        const shown = notes.filter(n => {
            const text = `${n.title} ${n.unit || ""} ${n.subject || ""} ${n.description || ""}`.toLowerCase();
            return (year === "all" || n.year === year) &&
                (subject === "all" || n.subject === subject) && text.includes(q);
        });

        countText.textContent = shown.length + " note" + (shown.length === 1 ? "" : "s") + " for " + course;

        if (!notes.length) {
            showMessage(`<div class="ss-empty"><strong>No notes yet for ${esc(course)}</strong>
                <p>No notes are currently available for your course. You will get a notification as soon as one is uploaded.</p>
                <a class="ss-btn ss-btn-light" href="/courses">Explore other courses</a></div>`);
            return;
        }
        if (!shown.length) {
            showMessage(`<div class="ss-empty"><strong>No notes match your filters</strong>
                <p>Try a different search, subject or year.</p></div>`);
            return;
        }
        setBusy(false);
        list.className = "ss-notes-grid";
        list.innerHTML = shown.map(card).join("");
    }

    async function load() {
        list.className = "ss-notes-grid";
        setBusy(true);
        try {
            const response = await fetch("/api/notes?course=" + encodeURIComponent(course), { headers: { "Accept": "application/json" } });
            if (!response.ok) throw new Error("bad status");
            notes = await response.json();

            // Start on the student's own year when it has notes; otherwise show every year so the page is never empty by accident
            const useMine = myYear && notes.some(n => n.year === myYear);
            yearBox.value = useMine ? myYear : "all";
            fillSubjects();
            render();
        } catch (error) {
            countText.textContent = "";
            showMessage(`<div class="ss-empty ss-empty-error" role="alert"><strong>Could not load notes</strong>
                <p>Please check your connection and try again.</p>
                <button type="button" class="ss-btn" id="dnRetry">Try again</button></div>`);
            document.getElementById("dnRetry").addEventListener("click", () => { countText.textContent = "Loading notes..."; load(); });
        }
    }

    searchBox.addEventListener("input", render);
    subjectBox.addEventListener("change", render);
    yearBox.addEventListener("change", () => { fillSubjects(); render(); });

    load();
})();
