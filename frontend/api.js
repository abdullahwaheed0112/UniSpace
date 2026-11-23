// api.js: the one place that knows the API address and how the login session is stored.
// Every page loads config.js and then this file before its own scripts.

const Session = {
    // The token is what the server trusts. username and role are stored only so the UI can show the right links;
    // the server re-checks the token on every request, so editing these values in the browser grants nothing.
    save({ token, username, role }) {
        localStorage.setItem("token", token);
        localStorage.setItem("username", username);
        localStorage.setItem("role", role);
    },
    clear() {
        ["token", "username", "role"].forEach((key) => localStorage.removeItem(key));
    },
    get token() { return localStorage.getItem("token"); },
    get username() { return localStorage.getItem("username"); },
    get role() { return localStorage.getItem("role"); },
    get isLoggedIn() { return Boolean(localStorage.getItem("token")); },
};

// apiFetch("/bookings", { method: "POST", body: {...}, auth: true })
// Returns { ok, status, data }. If the server says the session is invalid (401) the user is sent to the sign-in page.
async function apiFetch(path, { method = "GET", body, auth = true } = {}) {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && Session.token) headers["Authorization"] = "Bearer " + Session.token;

    const response = await fetch(window.UNISPACE_API_BASE + path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    let data = null;
    try {
        data = await response.json();
    } catch (err) {
        // empty or non-JSON body
    }

    if (response.status === 401 && auth && Session.token) {
        Session.clear();
        window.location.href = "signin.html?expired=1";
    }
    return { ok: response.ok, status: response.status, data };
}
