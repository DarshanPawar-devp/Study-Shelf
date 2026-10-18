/* ==========================================================
   StudyShelf - admins.js
   Job of this file (admin only, used on the "Manage admins" page):
   1. Open the popup to add an admin
   2. Open the same popup to change an admin's password
   3. Save the popup (POST for new, PUT for password change)
   4. Delete an admin after asking for confirmation
   After every change the page reloads so the list is up to date.
   ========================================================== */

const modal = document.getElementById("adminModal");
const form = document.getElementById("adminForm");
const title = document.getElementById("adminModalTitle");
const hint = document.getElementById("adminModalHint");
const usernameLabel = document.getElementById("usernameLabel");
const usernameInput = document.getElementById("adminUsername");
const passwordInput = document.getElementById("adminPassword");
const passwordLabel = document.getElementById("passwordLabel");
const message = document.getElementById("adminMessage");
const labelText = document.getElementById("usernameLabelText");

// null = adding a new admin, otherwise the username being edited
let editingUser = null;
// "password" = changing the password, "rename" = changing the username
let editMode = "password";


function openModal() {
    message.textContent = "";
    if (typeof modal.showModal === "function") {
        modal.showModal();
    } else {
        modal.setAttribute("open", "");   // fallback for old browsers
    }
}


/* ---------- 1. ADD ---------- */
const addButton = document.getElementById("addAdminBtn");   // only the owner has this button
if (addButton) addButton.addEventListener("click", () => {
    editingUser = null;
    editMode = "password";
    form.reset();
    passwordLabel.style.display = "";
    passwordInput.required = true;
    title.textContent = "Add admin";
    hint.textContent = "Username: letters, numbers, dots, dashes. Password: at least 6 characters.";
    usernameLabel.style.display = "";
        labelText.textContent = "Username";
        usernameInput.maxLength = 30;
    usernameInput.required = true;
    openModal();
    usernameInput.focus();
});


/* ---------- 2. CHANGE PASSWORD ---------- */
document.querySelectorAll(".change-pass").forEach(button => {
    button.addEventListener("click", () => {
        editingUser = button.dataset.user;
        editMode = "password";
        form.reset();
        passwordLabel.style.display = "";
        passwordInput.required = true;
        title.textContent = "New password for " + editingUser;
        hint.textContent = "The old password stops working straight away.";
        usernameLabel.style.display = "none";   // the username cannot be changed
        usernameInput.required = false;
        openModal();
        passwordInput.focus();
    });
});


/* ---------- 2b. RENAME ---------- */
document.querySelectorAll(".rename-admin").forEach(button => {
    button.addEventListener("click", () => {
        editingUser = button.dataset.user;
        editMode = "rename";
        form.reset();
        title.textContent = "Rename " + editingUser;
        hint.textContent = "The password stays the same. Use the new username next time you log in.";
        usernameLabel.style.display = "";
        labelText.textContent = "Username";
        usernameInput.maxLength = 30;
        usernameInput.required = true;
        usernameInput.value = editingUser;
        passwordLabel.style.display = "none";   // no password needed to rename
        passwordInput.required = false;
        openModal();
        usernameInput.focus();
    });
});


/* ---------- 2c. DISPLAY NAME (shown as "Uploaded by") ---------- */
document.querySelectorAll(".display-admin").forEach(button => {
    button.addEventListener("click", () => {
        editingUser = button.dataset.user;
        editMode = "display";
        form.reset();
        title.textContent = "Display name for " + editingUser;
        hint.textContent = "Shown as \"Uploaded by\" on this admin's notes, e.g. Faculty 1. Leave empty to show \"Admin\".";
        labelText.textContent = "Display name";
        usernameLabel.style.display = "";
        usernameInput.required = false;
        usernameInput.maxLength = 40;
        usernameInput.value = button.dataset.name || "";
        passwordLabel.style.display = "none";
        passwordInput.required = false;
        openModal();
        usernameInput.focus();
    });
});


/* ---------- 3. SAVE ---------- */
form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "Saving...";

    let url = "/api/admins";
    let method = "POST";
    let body = { username: usernameInput.value, password: passwordInput.value };

    if (editingUser && editMode === "display") {
        url = "/api/admins/" + encodeURIComponent(editingUser) + "/display-name";
        method = "PUT";
        body = { display_name: usernameInput.value };
    } else if (editingUser && editMode === "rename") {
        url = "/api/admins/" + encodeURIComponent(editingUser) + "/rename";
        method = "PUT";
        body = { username: usernameInput.value };
    } else if (editingUser) {
        url = "/api/admins/" + encodeURIComponent(editingUser);
        method = "PUT";
        body = { password: passwordInput.value };
    }

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
            message.textContent = data.error || "Could not save.";
        }
    } catch (error) {
        message.textContent = "Server error. Please try again.";
    }
});

document.getElementById("adminClose").addEventListener("click", () => modal.close());


/* ---------- 4. DELETE ---------- */
document.querySelectorAll(".delete-admin").forEach(button => {
    button.addEventListener("click", async () => {
        const user = button.dataset.user;
        if (!confirm("Delete admin " + user + "? They will not be able to log in any more.")) return;

        const response = await fetch("/api/admins/" + encodeURIComponent(user), { method: "DELETE" });

        if (response.ok) {
            location.reload();
        } else {
            const data = await response.json().catch(() => ({}));
            alert(data.error || "Could not delete. Please log in as admin again.");
        }
    });
});
