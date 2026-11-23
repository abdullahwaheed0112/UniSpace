// ui.js: small helpers shared by every page.

// Turn text into something that is safe to put inside HTML. Anything that came from the server or a user
// (usernames, resource names, notification text, reasons) must pass through this before it is placed in
// innerHTML, otherwise text like <img onerror=...> would run as code in the admin's browser.
function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[ch]));
}

// A status as a coloured chip. The text is always shown, colour is only a hint.
function statusChip(status) {
    return `<span class="chip" data-status="${escapeHtml(status)}">${escapeHtml(status)}</span>`;
}

// ---- dates (ISO strings like "2026-11-24", handled in local time so there are no timezone surprises) ----
function isoDate(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseIso(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
}

function formatDay(iso) {
    return parseIso(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

function formatLongDay(iso) {
    return parseIso(iso).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

// The next `count` calendar days that fall on a weekday, starting today (resources are bookable Monday to Friday).
function upcomingWeekdays(count = 7) {
    const days = [];
    for (let i = 0; i < count; i++) {
        const d = new Date();
        d.setDate(d.getDate() + i);
        if (d.getDay() !== 0 && d.getDay() !== 6) days.push(isoDate(d));
    }
    return days;
}

// ---- feedback ----
function showNotice(element, kind, text) {
    element.dataset.kind = kind;
    element.textContent = text || "";
}

// Ask for a short written reason in a native <dialog>. Resolves to the text, or null if the person cancelled.
function askReason({ title, message = "", confirmLabel = "Confirm", required = true, danger = false }) {
    return new Promise((resolve) => {
        const dialog = document.createElement("dialog");
        dialog.innerHTML = `
            <form method="dialog">
                <h2>${escapeHtml(title)}</h2>
                ${message ? `<p class="muted">${escapeHtml(message)}</p>` : ""}
                <div class="field">
                    <label for="reason-text">Reason${required ? "" : " (optional)"}</label>
                    <textarea id="reason-text" maxlength="200" ${required ? "required" : ""}></textarea>
                </div>
                <div class="row">
                    <button class="btn" value="cancel" formnovalidate>Cancel</button>
                    <button class="btn ${danger ? "btn-danger" : "btn-primary"}" value="ok">${escapeHtml(confirmLabel)}</button>
                </div>
            </form>`;
        document.body.appendChild(dialog);
        dialog.addEventListener("close", () => {
            const confirmed = dialog.returnValue === "ok";
            const text = dialog.querySelector("textarea").value.trim();
            dialog.remove();
            resolve(confirmed ? text : null);
        });
        dialog.showModal();
        dialog.querySelector("textarea").focus();
    });
}
