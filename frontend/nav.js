// nav.js: draws the header (and footer) on every page and, for students, the notifications menu.
// The header is built from the verified session: the role comes from the server (GET /me), not from local storage.

(async function renderChrome() {
    const header = document.getElementById("site-header");
    const footer = document.getElementById("site-footer");
    const page = location.pathname.split("/").pop() || "index.html";

    let session = Session.isLoggedIn ? { username: Session.username, role: Session.role } : null;
    if (session) {
        try {
            const { ok, data } = await apiFetch("/me");
            if (ok) {
                session = data;
                Session.save({ token: Session.token, username: data.username, role: data.role });
            }
        } catch (err) {
            // The API is unreachable: fall back to what we have so the page still renders.
        }
    }

    const link = (href, label) =>
        `<a href="${href}"${page === href ? ' aria-current="page"' : ""}>${escapeHtml(label)}</a>`;

    let links;
    if (!session) {
        links = link("resources.html", "Availability") + link("signin.html", "Sign in") + link("signup.html", "Create account");
    } else if (session.role === "admin") {
        links = link("dashboard.html", "Requests") + link("resources.html", "Availability") +
            `<span class="who">${escapeHtml(session.username)}</span><button class="linklike" id="sign-out" type="button">Sign out</button>`;
    } else {
        links = link("booking.html", "Book a space") + link("mybookings.html", "My bookings") + link("resources.html", "Availability") +
            `<details class="notifs" id="notifs"><summary>Notifications<span class="count" id="notif-count" hidden></span></summary>` +
            `<div class="notif-panel" id="notif-panel"><p class="none">Loading…</p></div></details>` +
            `<span class="who">${escapeHtml(session.username)}</span><button class="linklike" id="sign-out" type="button">Sign out</button>`;
    }

    if (header) {
        header.className = "site-header";
        header.innerHTML = `<div class="bar"><a class="brand" href="index.html">Uni<span>Space</span></a><nav class="site-nav" aria-label="Main">${links}</nav></div>`;
        const signOut = document.getElementById("sign-out");
        if (signOut) {
            signOut.addEventListener("click", () => {
                Session.clear();
                window.location.href = "index.html";
            });
        }
    }
    if (footer) {
        footer.className = "site-footer";
        footer.innerHTML = '<div class="bar">UniSpace: campus room and lab booking. A university group project built with Flask and MySQL.</div>';
    }

    if (session && session.role === "student") setupNotifications();
})();

async function setupNotifications() {
    const details = document.getElementById("notifs");
    const panel = document.getElementById("notif-panel");
    const count = document.getElementById("notif-count");
    if (!details || !panel) return;

    let unread = 0;
    async function load() {
        const { ok, data } = await apiFetch("/notifications");
        if (!ok || !Array.isArray(data)) {
            panel.innerHTML = '<p class="none">Could not load notifications.</p>';
            return;
        }
        unread = data.filter((n) => !n.is_read).length;
        count.textContent = unread;
        count.hidden = unread === 0;
        panel.innerHTML = data.length === 0
            ? '<p class="none">Nothing yet. Updates about your bookings will appear here.</p>'
            : `<ul>${data.map((n) => `<li data-unread="${!n.is_read}">${escapeHtml(n.message)}<span class="when">${escapeHtml(n.date)}</span></li>`).join("")}</ul>`;
    }

    details.addEventListener("toggle", async () => {
        if (!details.open || unread === 0) return;
        await apiFetch("/notifications/read", { method: "PUT" });
        count.hidden = true;
        unread = 0;
        // keep the highlight for this viewing, clear it next time
        setTimeout(() => panel.querySelectorAll("li[data-unread='true']").forEach((li) => li.removeAttribute("data-unread")), 4000);
    });
    document.addEventListener("click", (event) => { if (!details.contains(event.target)) details.open = false; });

    await load();
}
