/* ==========================================================
   StudyShelf - profile.js  (loaded for logged-in students on every page)
   1. Avatar button opens a small profile pop-up (name, email, course, year)
   2. "Edit details" opens a dialog with the name / course / year form
   3. Saves with the existing PUT /api/profile (the server checks everything again)
   Pop-ups close on outside click and Escape.
   ========================================================== */
(function () {
    const root = document.getElementById("ssProfileRoot");
    if (!root) return;

    const avatar = document.getElementById("ssAvatar");
    const panel = document.getElementById("ssProfilePanel");
    const dialog = document.getElementById("ssEditDialog");
    const form = document.getElementById("ssEditForm");
    const nameInput = document.getElementById("ssEditName");
    const emailInput = document.getElementById("ssEditEmail");
    const courseSelect = document.getElementById("ssEditCourse");
    const yearSelect = document.getElementById("ssEditYear");
    const saveButton = document.getElementById("ssEditSave");
    const msg = document.getElementById("ssEditMsg");

    let profile = null;

    function say(text, ok) {
        msg.hidden = !text;
        msg.textContent = text || "";
        msg.className = "ss-alert " + (ok ? "ss-alert-ok" : "ss-alert-error");
    }

    /* ----- load the details once (and again after a failed try) ----- */
    async function load() {
        if (profile) return profile;
        const response = await fetch("/api/profile", { headers: { "Accept": "application/json" } });
        if (response.status === 401) { location.href = "/student/login"; throw new Error("login"); }
        if (!response.ok) throw new Error("bad status");
        profile = await response.json();
        return profile;
    }

    function fillPanel(p) {
        document.getElementById("ssPName").textContent = p.full_name;
        document.getElementById("ssPEmail").textContent = p.email || "";
        document.getElementById("ssPCourse").textContent = p.course ? p.course + (p.course_name ? " - " + p.course_name : "") : "Not selected";
        document.getElementById("ssPYear").textContent = p.year ? p.year + (p.year_name ? " - " + p.year_name : "") : "All years";
        document.getElementById("ssPErr").hidden = true;
    }

    /* ----- profile pop-up ----- */
    function setOpen(open) {
        panel.hidden = !open;
        avatar.setAttribute("aria-expanded", String(open));
        if (open) {
            load().then(fillPanel).catch(() => {
                document.getElementById("ssPEmail").textContent = "";
                document.getElementById("ssPErr").hidden = false;
            });
        }
    }
    avatar.addEventListener("click", () => setOpen(panel.hidden));

    // Capture phase: still runs when another widget (the bell) stops the click from bubbling
    document.addEventListener("click", (e) => {
        if (!panel.hidden && !root.contains(e.target)) setOpen(false);
    }, true);
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !panel.hidden) { setOpen(false); avatar.focus(); }
    });

    /* ----- edit dialog ----- */
    function option(value, label) {
        const o = document.createElement("option");
        o.value = value; o.textContent = label;
        return o;
    }

    function fillYears(keep) {
        const count = profile.courses[courseSelect.value] ? profile.courses[courseSelect.value].years : 0;
        yearSelect.replaceChildren(option("", "All years"));
        profile.years_order.slice(0, count).forEach(code => yearSelect.appendChild(option(code, code + " - " + profile.year_names[code])));
        yearSelect.value = profile.years_order.slice(0, count).includes(keep) ? keep : "";
    }

    function fillForm() {
        nameInput.value = profile.full_name;
        emailInput.value = profile.email || "";
        courseSelect.replaceChildren(option("", "Choose your course"));
        Object.entries(profile.courses).forEach(([code, c]) => courseSelect.appendChild(option(code, code + " - " + c.name)));
        courseSelect.value = profile.course;
        fillYears(profile.year);
    }
    courseSelect.addEventListener("change", () => fillYears(""));

    async function openEdit() {
        setOpen(false);
        say("", true);
        try {
            await load();
            fillForm();
        } catch (error) {
            say("Could not load your details. Please try again.", false);
        }
        if (!dialog.open) dialog.showModal();
        nameInput.focus();
    }

    // Any button marked data-ss-edit opens it (the avatar pop-up, "Choose your course" on the dashboard)
    document.addEventListener("click", (e) => {
        if (e.target.closest("[data-ss-edit]")) openEdit();
    });

    document.getElementById("ssEditClose").addEventListener("click", () => dialog.close());
    document.getElementById("ssEditCancel").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });   // click on the dark area
    dialog.addEventListener("close", () => avatar.focus());

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const body = { full_name: nameInput.value.trim(), course: courseSelect.value, year: yearSelect.value };
        if (!body.full_name) { say("Please enter your name.", false); nameInput.focus(); return; }
        if (!body.course) { say("Please choose a course.", false); courseSelect.focus(); return; }

        say("Saving...", true);
        saveButton.disabled = true;
        try {
            const response = await fetch("/api/profile", {
                method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
            });
            const data = await response.json().catch(() => ({}));
            if (response.ok) {
                say("Saved.", true);
                // Reload so the greeting, initials and the notes of the (new) course are all up to date
                setTimeout(() => location.reload(), 500);
            } else {
                say(data.error || "Could not save. Please try again.", false);
                saveButton.disabled = false;
            }
        } catch (error) {
            say("Server error. Please try again.", false);
            saveButton.disabled = false;
        }
    });
})();
