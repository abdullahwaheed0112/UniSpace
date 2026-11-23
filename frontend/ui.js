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
