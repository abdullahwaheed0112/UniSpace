// auth.js: the sign-in and sign-up forms.

const message = document.getElementById("message");

const signinForm = document.getElementById("signinForm");
if (signinForm) {
    if (new URLSearchParams(location.search).get("expired")) {
        showNotice(message, "error", "Your session has expired. Please sign in again.");
    }

    signinForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value;
        if (!email || !password) {
            showNotice(message, "error", "Enter your email and password.");
            return;
        }
        try {
            const { ok, data } = await apiFetch("/signin", { method: "POST", body: { email, password }, auth: false });
            if (ok) {
                Session.save(data);
                window.location.href = data.role === "admin" ? "dashboard.html" : "index.html";
            } else {
                showNotice(message, "error", data?.message || "Could not sign in.");
            }
        } catch (err) {
            showNotice(message, "error", "Could not reach the server. Is it running?");
        }
    });
}

const signupForm = document.getElementById("signupForm");
if (signupForm) {
    signupForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const username = document.getElementById("username").value.trim();
        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value;
        if (password.length < 8) {
            showNotice(message, "error", "The password needs at least 8 characters.");
            return;
        }
        try {
            const { ok, data } = await apiFetch("/signup", { method: "POST", body: { username, email, password }, auth: false });
            if (ok) {
                signupForm.reset();
                showNotice(message, "success", "Account created. You can sign in now.");
            } else {
                showNotice(message, "error", data?.message || "Could not create the account.");
            }
        } catch (err) {
            showNotice(message, "error", "Could not reach the server. Is it running?");
        }
    });
}
