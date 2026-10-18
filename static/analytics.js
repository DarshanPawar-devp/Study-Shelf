/* ==========================================================
   StudyShelf - analytics.js  (admin only)
   Loads /api/analytics?days=7|30 and draws the cards + 4 charts with Chart.js.
   All numbers come from the database. Nothing is made up.
   ========================================================== */
const cardsBox = document.getElementById("anCards");
const rangeText = document.getElementById("anRange");
const noteText = document.getElementById("anNote");
const msg = document.getElementById("anMsg");
const charts = {};

function esc(text) {
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
}

function shortDate(iso) {
    const d = new Date(iso + "T00:00:00Z");
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });
}

function draw(id, type, labels, datasets, extra) {
    if (charts[id]) charts[id].destroy();          // redraw cleanly when the range changes
    const options = {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: datasets.length > 1 || type === "doughnut" }, tooltip: { enabled: true } },
        scales: type === "doughnut" ? {} : { y: { beginAtZero: true, ticks: { precision: 0 } } }
    };
    charts[id] = new Chart(document.getElementById(id), { type, data: { labels, datasets }, options: Object.assign(options, extra || {}) });
}

async function loadAnalytics(days) {
    msg.hidden = true;
    cardsBox.innerHTML = '<p class="ss-muted ss-pad">Loading...</p>';
    let data;
    try {
        const response = await fetch("/api/analytics?days=" + days);
        if (!response.ok) throw new Error();
        data = await response.json();
    } catch (error) {
        cardsBox.innerHTML = "";
        msg.hidden = false;
        msg.className = "ss-alert ss-alert-error";
        msg.textContent = "Could not load analytics. Please log in as admin again.";
        return;
    }

    const c = data.cards;
    const period = shortDate(data.from_date) + " to " + shortDate(data.to_date);
    rangeText.textContent = "Selected period: " + period + " (UTC). \"Active now\" means activity in the last " +
        data.active_minutes + " minutes. It is based on recent requests, not proof that someone is looking at the screen.";

    const cards = [
        [c.total_students, "Registered students", "All time"],
        [c.active_now, "Active now", "Last " + data.active_minutes + " minutes"],
        [c.unique_today, "Students logged in today", "Today (UTC)"],
        [c.logins_period, "Successful login events", period],
        [c.unique_period, "Unique students who logged in", period],
        [c.new_period, "New registrations", period]
    ];
    cardsBox.innerHTML = cards.map(x =>
        `<div class="ss-stat"><span class="ss-stat-num">${esc(x[0])}</span><span class="ss-stat-label">${esc(x[1])}</span><small class="ss-muted">${esc(x[2])}</small></div>`).join("");

    // Honest note: history before tracking started does not exist
    if (!data.tracking_since) {
        noteText.textContent = "No student logins have been recorded yet. The login charts fill in as students log in.";
    } else {
        noteText.textContent = "Login tracking started on " + new Date(data.tracking_since).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) +
            ". Earlier days show 0 because nothing was recorded then. \"Students who logged in\" counts different students with at least one login that day.";
    }

    if (typeof Chart === "undefined") return;       // cards are shown, charts need the library
    const labels = data.labels.map(shortDate);
    draw("chDaily", "line", labels, [{ label: "Students who logged in", data: data.daily_active, borderColor: "#3478f6", backgroundColor: "#3478f633", fill: true, tension: 0.25 }]);
    draw("chSignups", "bar", labels, [{ label: "New registrations", data: data.signups, backgroundColor: "#74e0ca" }]);
    draw("chLogins", "line", labels, [{ label: "Login events", data: data.logins, borderColor: "#e8742f", backgroundColor: "#e8742f33", fill: true, tension: 0.25 }]);

    const palette = ["#3478f6", "#2e9d4f", "#e8742f", "#7c5cf5", "#d6407a", "#12a594", "#9aa5b8"];
    draw("chCourses", "doughnut", data.courses.map(x => x.course),
        [{ label: "Students", data: data.courses.map(x => x.students), backgroundColor: data.courses.map((x, i) => palette[i % palette.length]) }]);
    if (!data.courses.length) {
        noteText.textContent += " No students have registered yet, so the course chart is empty.";
    }
}

document.querySelectorAll(".ss-range-btn").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".ss-range-btn").forEach(b => b.classList.remove("is-on"));
        button.classList.add("is-on");
        loadAnalytics(Number(button.dataset.days));
    });
});

if (typeof Chart === "undefined") {
    msg.hidden = false;
    msg.className = "ss-alert ss-alert-error";
    msg.textContent = "The chart library could not load (check your internet connection).";
}
loadAnalytics(7);
