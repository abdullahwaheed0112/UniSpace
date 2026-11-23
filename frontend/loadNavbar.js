// Load the navbar into every page
fetch("navbar.html")
    .then(response => response.text())
    .then(html => {
        document.getElementById("navbar").innerHTML = html;
        updateNavbarLinks();
    });

function updateNavbarLinks() {
    const navLinks = document.getElementById("navLinks");
    const navGreeting = document.getElementById("navGreeting");
    if (!navLinks) return;

    // Check if user is logged in (from localStorage)
    const loggedInUser = localStorage.getItem("username");
    const userRole = localStorage.getItem("role");

    navLinks.innerHTML = ""; // Clear existing links
    
    // Set greeting
    if (navGreeting && loggedInUser) {
        navGreeting.innerHTML = `<span class="welcome-text"> Hello, ${loggedInUser}!</span>`;
        navGreeting.style.display = "block";
    } else if (navGreeting) {
        navGreeting.style.display = "none";
    }

    if (!loggedInUser) {
        // Not logged in
        navLinks.innerHTML = `
            <li><a href="resources.html" id="nav-resources">Resources</a></li>
            <li><a href="signin.html" id="nav-signin">Sign In</a></li>
        `;
    } else if (userRole === "admin") {
        // Logged in as Admin
        navLinks.innerHTML = `
            <li><a href="dashboard.html" id="nav-dashboard">Dashboard</a></li>
            <li><a href="resources.html" id="nav-resources">Resources</a></li>
            <li><a href="#" onclick="logout()">Sign Out</a></li>
        `;
    } else {
        // Logged in as Student
        navLinks.innerHTML = `
            <li><a href="booking.html" id="nav-booking">Booking</a></li>
            <li><a href="mybookings.html" id="nav-mybookings">My Bookings</a></li>
            <li><a href="resources.html" id="nav-resources">Resources</a></li>
            
            <li class="nav-item position-relative dropdown" style="display:flex; align-items:center; margin-left: 10px; margin-right: 10px;">
                <a class="nav-link notification-bell" href="#" id="notifDropdown" data-bs-toggle="dropdown" aria-expanded="false" onclick="markNotificationsRead()">
                    <i class="fa-solid fa-bell" style="color: rgba(255,255,255,0.75); transition: color 0.3s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='rgba(255,255,255,0.75)'"></i>
                    <span id="notifBadge" class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger notification-badge" style="display:none;">0</span>
                </a>
                <ul class="dropdown-menu dropdown-menu-end notif-dropdown-menu" aria-labelledby="notifDropdown" id="notifMenu">
                    <li class="notif-empty">Loading notifications...</li>
                </ul>
            </li>
            
            <li><a href="#" onclick="logout()">Sign Out</a></li>
        `;
        fetchNotifications();
    }

    // Set active class
    const path = window.location.pathname;
    if (path.includes("resources.html") && document.getElementById("nav-resources")) {
        document.getElementById("nav-resources").classList.add("active");
    } else if (path.includes("dashboard.html") && document.getElementById("nav-dashboard")) {
        document.getElementById("nav-dashboard").classList.add("active");
    } else if (path.includes("booking.html") && path.includes("mybookings.html") === false && document.getElementById("nav-booking")) {
        document.getElementById("nav-booking").classList.add("active");
    } else if (path.includes("mybookings.html") && document.getElementById("nav-mybookings")) {
        document.getElementById("nav-mybookings").classList.add("active");
    }
}

// Logout function
function logout() {
    Session.clear();
    window.location.href = "index.html"; // Redirect to home
}

// Notifications functions
async function fetchNotifications() {
    if (!Session.isLoggedIn) return;

    try {
        const { ok, data } = await apiFetch("/notifications");
        if (!ok || !Array.isArray(data)) return;
        const notifications = data;
        
        const notifBadge = document.getElementById("notifBadge");
        const notifMenu = document.getElementById("notifMenu");
        if (!notifBadge || !notifMenu) return;
        
        const unreadCount = notifications.filter(n => !n.is_read).length;
        
        if (unreadCount > 0) {
            notifBadge.textContent = unreadCount;
            notifBadge.style.display = "block";
        } else {
            notifBadge.style.display = "none";
        }
        
        notifMenu.innerHTML = "";
        
        if (notifications.length === 0) {
            notifMenu.innerHTML = `<li class="notif-empty">No notifications yet.</li>`;
        } else {
            notifications.forEach(n => {
                const li = document.createElement("li");
                li.className = `notif-item ${!n.is_read ? 'unread' : ''}`;
                li.innerHTML = `
                    ${n.message}
                    <span class="notif-date">${n.date}</span>
                `;
                notifMenu.appendChild(li);
            });
        }
    } catch (err) {
        console.error("Failed to fetch notifications", err);
    }
}

async function markNotificationsRead() {
    const username = localStorage.getItem("username");
    const notifBadge = document.getElementById("notifBadge");
    
    if (notifBadge && notifBadge.style.display !== "none") {
        try {
            await apiFetch("/notifications/read", { method: "PUT" });
            
            notifBadge.style.display = "none";
            
            document.querySelectorAll('.notif-item.unread').forEach(el => {
                el.classList.remove('unread');
            });
        } catch (err) {
            console.error("Failed to mark notifications read", err);
        }
    }
}
