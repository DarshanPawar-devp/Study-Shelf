/* ==========================================================
   StudyShelf - student.js  (loaded only for logged-in students)
   1. Loads notifications from /api/notifications
   2. Shows the number on the bell and the dropdown list
   3. Shows a small toast for NEW notifications (not on every refresh)
   4. Checks again every 60 seconds, only while the tab is visible
   There is no live connection to clean up: one small request a minute.
   ========================================================== */
(function () {
    const root = document.getElementById("ssRoot");
    if (!root) return;

    const uid = root.dataset.uid;
    const bell = document.getElementById("ssBell");
    const badge = document.getElementById("ssBadge");
    const panel = document.getElementById("ssPanel");
    const list = document.getElementById("ssList");
    const toasts = document.getElementById("ssToasts");
    const POLL_MS = 60000;

    let items = [];
    let lastLoad = 0;

    function esc(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function dateText(iso) {
        const d = new Date(iso);
        return isNaN(d) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    }

    /* The last notification id we already showed as a toast is kept in this browser.
       So a page refresh does not show the same toast again. */
    const seenKey = "ss_seen_" + uid;
    function getSeen() {
        try { const v = localStorage.getItem(seenKey); return v === null ? null : Number(v); } catch (e) { return null; }
    }
    function setSeen(n) {
        try { localStorage.setItem(seenKey, String(n)); } catch (e) { /* storage blocked: ignore */ }
    }

    function link(n) { return "/course/" + encodeURIComponent(n.course) + "?note=" + n.note_id; }

    /* ----- bell badge + dropdown ----- */
    function render(unread) {
        badge.hidden = unread <= 0;
        badge.textContent = unread > 99 ? "99+" : String(unread);
        bell.setAttribute("aria-label", unread > 0 ? "Notifications, " + unread + " unread" : "Notifications");

        if (!items.length) {
            list.innerHTML = '<p class="ss-muted ss-pad">No notifications yet. New notes for your course will appear here.</p>';
            return;
        }
        list.innerHTML = items.map(n => `
            <a class="ss-item ${n.read ? "" : "ss-unread"}" href="${link(n)}" data-ss-notif="${n.id}">
                <span class="ss-dot" aria-hidden="true"></span>
                <span class="ss-item-text">
                    <strong>New notes: ${esc(n.title)}</strong>
                    <span class="ss-muted">${esc(n.course)} &middot; ${esc(n.subject)} &middot; ${esc(dateText(n.created_at))} &middot; ${n.read ? "Read" : "Unread"}</span>
                </span>
            </a>`).join("");
    }

    /* ----- toasts ----- */
    function closeToast(el) { el.classList.add("ss-out"); setTimeout(() => el.remove(), 200); }

    function showToast(html) {
        const el = document.createElement("div");
        el.className = "ss-toast";
        el.setAttribute("role", "status");
        el.innerHTML = html + '<button type="button" class="ss-toast-x" aria-label="Dismiss">&times;</button>';
        el.querySelector(".ss-toast-x").addEventListener("click", () => closeToast(el));
        toasts.appendChild(el);
        setTimeout(() => { if (el.isConnected) closeToast(el); }, 12000);   // dismissing never deletes the notification
        while (toasts.children.length > 3) toasts.firstChild.remove();
    }

    function toastNew(latestId) {
        const seen = getSeen();
        if (seen === null) { setSeen(latestId); return; }          // first visit in this browser: no pop-up flood
        const fresh = items.filter(n => !n.read && n.id > seen);
        if (fresh.length === 1) {
            const n = fresh[0];
            showToast(`<strong>New notes available!</strong>
                <p>&ldquo;${esc(n.title)}&rdquo; has been uploaded for your ${esc(n.course)} course.</p>
                <a class="ss-toast-btn" href="${link(n)}" data-ss-notif="${n.id}">View notes</a>`);
        } else if (fresh.length > 1) {
            showToast(`<strong>${fresh.length} new notes available!</strong>
                <p>New material was uploaded for your course.</p>
                <a class="ss-toast-btn" href="/notifications">View all</a>`);
        }
        if (latestId > seen) setSeen(latestId);
    }

    /* ----- loading ----- */
    async function load() {
        lastLoad = Date.now();
        try {
            const response = await fetch("/api/notifications", { headers: { "Accept": "application/json" } });
            if (response.status === 401) { location.href = "/student/login"; return; }
            if (!response.ok) throw new Error("bad status");
            const data = await response.json();
            items = data.items;
            render(data.unread);
            toastNew(data.latest_id);
        } catch (error) {
            if (!items.length) list.innerHTML = '<p class="ss-muted ss-pad">Could not load notifications. Try again later.</p>';
        }
    }

    /* ----- open / close the dropdown ----- */
    function setOpen(open) {
        panel.hidden = !open;
        bell.setAttribute("aria-expanded", String(open));
        if (open && Date.now() - lastLoad > 15000) load();
    }
    bell.addEventListener("click", (e) => { e.stopPropagation(); setOpen(panel.hidden); });
    document.addEventListener("click", (e) => { if (!panel.hidden && !root.contains(e.target)) setOpen(false); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) { setOpen(false); bell.focus(); } });

    /* ----- mark as read ----- */
    async function post(url) {
        try { await fetch(url, { method: "POST", keepalive: true }); } catch (e) { /* ignore */ }
    }

    async function markAll() {
        await post("/api/notifications/read-all");
        await load();
    }
    document.getElementById("ssMarkAll").addEventListener("click", markAll);
    const pageMarkAll = document.getElementById("pageMarkAll");
    if (pageMarkAll) pageMarkAll.addEventListener("click", async () => { await post("/api/notifications/read-all"); location.reload(); });

    // Clicking any notification (dropdown, page, dashboard or toast): mark it read, then open the note
    document.addEventListener("click", async (e) => {
        const a = e.target.closest("[data-ss-notif]");
        if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        await post("/api/notifications/" + a.dataset.ssNotif + "/read");
        location.href = a.getAttribute("href");
    });

    document.querySelectorAll("[data-ss-date]").forEach(t => { t.textContent = dateText(t.getAttribute("datetime")) || t.textContent; });

    /* ----- check again every minute, only while the tab is visible ----- */
    const timer = setInterval(() => { if (document.visibilityState === "visible") load(); }, POLL_MS);
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible" && Date.now() - lastLoad > 30000) load();
    });
    window.addEventListener("pagehide", () => clearInterval(timer));

    load();
})();
