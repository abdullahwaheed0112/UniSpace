// Sign Up Logic
const form = document.getElementById("signupForm");
const message = document.getElementById("message");

form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const username = document.getElementById("username").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    if (password.length < 6) {
        message.textContent = "Password must be at least 6 characters!";
        message.className = "error";
        return;
    }

    // Send sign-up data to the backend
    const response = await fetch("http://localhost:5000/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password })
    });

    const result = await response.json();

    if (response.ok) {
        message.textContent = result.message;
        message.className = "success";
        form.reset();
    } else {
        message.textContent = result.message;
        message.className = "error";
    }
});
