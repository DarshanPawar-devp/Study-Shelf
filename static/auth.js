/* ==========================================================
   StudyShelf - auth.js
   Used by the student login / register / reset pages and the dashboard.
   1. Show / hide password
   2. Year dropdown that follows the chosen course
   3. Save profile changes (dashboard)
   4. Set a new password after the reset email link
   ========================================================== */

// 1. Show / hide password
document.querySelectorAll("[data-toggle-pw]").forEach(button => {
    button.addEventListener("click", () => {
        const input = button.parentElement.querySelector("input");
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        button.textContent = show ? "Hide" : "Show";
    });
});

// 2. Year dropdown: a 3-year course shows FY, SY, TY; a 5-year course shows five years
const courseSelect = document.getElementById("course");
const yearSelect = document.getElementById("year");
function fillYears() {
    if (!courseSelect || !yearSelect) return;
    const courses = JSON.parse(courseSelect.dataset.courses);
    const order = JSON.parse(courseSelect.dataset.order);
    const names = JSON.parse(courseSelect.dataset.names);
    const keep = yearSelect.value || courseSelect.dataset.selectedYear || "";
    const count = courses[courseSelect.value] ? courses[courseSelect.value].years : 0;
    yearSelect.innerHTML = '<option value="">All years</option>' +
        order.slice(0, count).map(code => `<option value="${code}">${code} - ${names[code]}</option>`).join("");
    yearSelect.value = order.slice(0, count).includes(keep) ? keep : "";
}
if (courseSelect) {
    courseSelect.addEventListener("change", () => { courseSelect.dataset.selectedYear = ""; yearSelect.value = ""; fillYears(); });
    fillYears();
}

function say(element, text, ok) {
    element.hidden = false;
    element.textContent = text;
    element.className = "ss-alert " + (ok ? "ss-alert-ok" : "ss-alert-error");
}

// 3. Dashboard: save name / course / year
const profileForm = document.getElementById("profileForm");
if (profileForm) {
    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const msg = document.getElementById("profileMsg");
        const body = {
            full_name: profileForm.full_name.value,
            course: profileForm.course.value,
            year: profileForm.year.value
        };
        if (!body.course) { say(msg, "Please choose a course.", false); return; }
        say(msg, "Saving...", true);
        try {
            const response = await fetch("/api/profile", {
                method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
            });
            const data = await response.json().catch(() => ({}));
            if (response.ok) { say(msg, "Saved.", true); setTimeout(() => location.reload(), 600); }
            else say(msg, data.error || "Could not save.", false);
        } catch (error) {
            say(msg, "Server error. Please try again.", false);
        }
    });
}

// 4. Reset password. The email link opens this page with a one-time token after the "#".
//    The browser sends the new password straight to Supabase Auth with that token.
const resetForm = document.getElementById("resetForm");
if (resetForm) {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    const token = params.get("access_token");
    const msg = document.getElementById("resetMsg");
    if (!token) {
        say(msg, "This reset link is missing or has expired. Please request a new one.", false);
        resetForm.hidden = true;
    }
    resetForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const password = document.getElementById("newPassword").value;
        if (password.length < 8) { say(msg, "Password must be at least 8 characters.", false); return; }
        say(msg, "Saving...", true);
        try {
            const response = await fetch(resetForm.dataset.url + "/auth/v1/user", {
                method: "PUT",
                headers: { "Content-Type": "application/json", "apikey": resetForm.dataset.key, "Authorization": "Bearer " + token },
                body: JSON.stringify({ password })
            });
            if (response.ok) {
                history.replaceState(null, "", location.pathname);    // remove the token from the address bar
                resetForm.hidden = true;
                say(msg, "Password changed. You can log in now.", true);
            } else {
                const data = await response.json().catch(() => ({}));
                say(msg, data.msg || data.message || "Could not change the password. Request a new link.", false);
            }
        } catch (error) {
            say(msg, "Could not reach the server. Please try again.", false);
        }
    });
}
