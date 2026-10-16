/* ==========================================================
   StudyShelf - manage.js
   Job of this file (admin only, used on the "Manage courses" page):
   1. Open the popup to add a course
   2. Open the same popup filled in to edit a course
   3. Save the popup (POST for new, PUT for edit)
   4. Delete a course after asking for confirmation
   After every change the page reloads so the list is up to date.
   ========================================================== */

const modal = document.getElementById("courseModal");
const form = document.getElementById("courseForm");
const title = document.getElementById("courseModalTitle");
const codeInput = document.getElementById("courseCode");
const nameInput = document.getElementById("courseName");
const yearsInput = document.getElementById("courseYears");
const message = document.getElementById("courseMessage");

// null = adding a new course, otherwise the code of the course being edited
let editingCode = null;


function openModal() {
    message.textContent = "";
    if (typeof modal.showModal === "function") {
        modal.showModal();
    } else {
        modal.setAttribute("open", "");   // fallback for old browsers
    }
}


/* ---------- 1. ADD ---------- */
document.getElementById("addCourseBtn").addEventListener("click", () => {
    editingCode = null;
    form.reset();
    title.textContent = "Add course";
    codeInput.disabled = false;   // the code can be typed for a new course
    openModal();
    codeInput.focus();
});


/* ---------- 2. EDIT ----------
   The values are stored in data-... attributes on each Edit button. */
document.querySelectorAll(".edit-course").forEach(button => {
    button.addEventListener("click", () => {
        editingCode = button.dataset.code;
        title.textContent = "Edit " + editingCode;
        codeInput.value = editingCode;
        codeInput.disabled = true;   // the code is fixed once the course exists
        nameInput.value = button.dataset.name;
        yearsInput.value = button.dataset.years;
        openModal();
        nameInput.focus();
    });
});


/* ---------- 3. SAVE ---------- */
form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "Saving...";

    const body = {
        code: codeInput.value,
        name: nameInput.value,
        years: yearsInput.value
    };

    // New course -> POST /api/courses.  Existing course -> PUT /api/courses/<code>
    const url = editingCode ? "/api/courses/" + encodeURIComponent(editingCode) : "/api/courses";
    const method = editingCode ? "PUT" : "POST";

    try {
        const response = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });

        if (response.ok) {
            location.reload();
        } else {
            const data = await response.json().catch(() => ({}));
            message.textContent = data.error || "Could not save the course.";
        }
    } catch (error) {
        message.textContent = "Server error. Please try again.";
    }
});

document.getElementById("courseClose").addEventListener("click", () => modal.close());


/* ---------- 4. DELETE ---------- */
document.querySelectorAll(".delete-course").forEach(button => {
    button.addEventListener("click", async () => {
        const code = button.dataset.code;
        const notes = Number(button.dataset.notes);

        // Say clearly what will be lost before deleting
        const warning = notes > 0
            ? "Delete " + code + " and its " + notes + " note" + (notes === 1 ? "" : "s") +
              " (including uploaded files)? This cannot be undone."
            : "Delete " + code + "? This cannot be undone.";
        if (!confirm(warning)) return;

        const response = await fetch("/api/courses/" + encodeURIComponent(code), { method: "DELETE" });

        if (response.ok) {
            location.reload();
        } else {
            alert("Could not delete. Please log in as admin again.");
        }
    });
});
