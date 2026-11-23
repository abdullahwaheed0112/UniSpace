// --- SIGN IN LOGIC ---
const signinForm = document.getElementById("signinForm");
if (signinForm) {
    const message = document.getElementById("message");

    signinForm.addEventListener("submit", async function (e) {
        e.preventDefault();

        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;

        try {
            const { ok, data: result } = await apiFetch("/signin", { method: "POST", body: { email, password }, auth: false });

            if (ok) {
                Session.save(result);

                message.textContent = result.message;
                message.className = "success";

                setTimeout(() => {
                    window.location.href = "index.html";
                }, 1000);
            } else {
                message.textContent = result.message;
                message.className = "error";
                setTimeout(() => {
                    message.textContent = "";
                    message.className = "";
                }, 3000);
            }
        } catch(err) {
            console.error("Sign in error:", err);
            message.textContent = "Unable to connect to server.";
            message.className = "error";
        }
    });
}

// --- BOOKING LOGIC ---
const bookingForm = document.getElementById("bookingForm");
const dateSelect = document.getElementById("date");
const timeSlotSelect = document.getElementById("timeSlot");

if (dateSelect && timeSlotSelect) {
    // Define available time slots up to 5 PM
    const timeSlots = [
        { value: "9-10", label: "9:00 AM - 10:00 AM", startHour: 9 },
        { value: "10-11", label: "10:00 AM - 11:00 AM", startHour: 10 },
        { value: "11-12", label: "11:00 AM - 12:00 PM", startHour: 11 },
        { value: "1-2", label: "1:00 PM - 2:00 PM", startHour: 13 },
        { value: "2-3", label: "2:00 PM - 3:00 PM", startHour: 14 },
        { value: "3-4", label: "3:00 PM - 4:00 PM", startHour: 15 },
        { value: "4-5", label: "4:00 PM - 5:00 PM", startHour: 16 }
    ];

    function populateDates() {
        const today = new Date();
        const currentHour = today.getHours();
        
        // If it's past 4 PM, skip today, start from tomorrow
        let startDay = currentHour >= 16 ? 1 : 0;
        
        for (let i = startDay; i <= 7; i++) {
            const nextDate = new Date(today);
            nextDate.setDate(today.getDate() + i);
            const offset = nextDate.getTimezoneOffset();
            const localDate = new Date(nextDate.getTime() - (offset * 60 * 1000));
            const value = localDate.toISOString().split("T")[0];
            
            let text;
            if (i === 0) {
                text = "Today, " + nextDate.toLocaleDateString("en-US", { month: "short", day: "numeric" });
            } else if (i === 1 && startDay === 0) {
                text = "Tomorrow, " + nextDate.toLocaleDateString("en-US", { month: "short", day: "numeric" });
            } else {
                text = nextDate.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
            }

            const option = document.createElement("option");
            option.value = value;
            option.textContent = text;
            dateSelect.appendChild(option);
        }
    }

    function populateTimeSlots(selectedDateValue) {
        // Reset slots
        timeSlotSelect.innerHTML = '<option value="">Choose a time slot</option>';
        if (!selectedDateValue) return;

        const today = new Date();
        const isToday = selectedDateValue === today.toISOString().split("T")[0];
        const currentHour = today.getHours();

        timeSlots.forEach(slot => {
            // For today, only show slots that are at least 1 hour from now
            if (isToday && slot.startHour <= currentHour + 1) return;

            const option = document.createElement("option");
            option.value = slot.value;
            option.textContent = slot.label;
            timeSlotSelect.appendChild(option);
        });
    }

    // When a date is selected, dynamically generate available time slots
    dateSelect.addEventListener("change", (e) => populateTimeSlots(e.target.value));

    // Initialize the date dropdown
    populateDates();

    // Pre-fill form from URL parameters if present
    const urlParams = new URLSearchParams(window.location.search);
    const preResource = urlParams.get('resource');
    const preDate = urlParams.get('date');
    const preTime = urlParams.get('timeSlot');

    if (preResource) {
        const resSelect = document.getElementById("resource");
        if (resSelect) resSelect.value = preResource;
    }
    if (preDate) {
        dateSelect.value = preDate;
        populateTimeSlots(preDate);
        if (preTime) {
            timeSlotSelect.value = preTime;
        }
    }

    // Fetch blocked slots to disable submitting early
    window.blockedSlots = [];
    apiFetch("/blocked_slots", { auth: false })
        .then(({ data }) => { window.blockedSlots = Array.isArray(data) ? data : []; })
        .catch(err => console.error(err));
}

if (bookingForm) {
    bookingForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        const resource = document.getElementById("resource").value;
        const date = dateSelect.value;
        const timeSlot = timeSlotSelect.value;
        const username = localStorage.getItem("username");

        if (!resource || !date || !timeSlot || !username) {
            alert("Please fill in all fields.");
            return;
        }

        // Check against fetched blocked slots
        const isBlocked = window.blockedSlots.some(slot => slot.resource === resource && slot.date === date && slot.time === timeSlot);
        if (isBlocked) {
            const blockedMsg = document.getElementById("blockedMessage");
            if (blockedMsg) {
                blockedMsg.style.display = "block";
                setTimeout(() => blockedMsg.style.display = "none", 4000);
            }
            return;
        }

        try {
            const { ok, data: result } = await apiFetch("/bookings", { method: "POST", body: { username, resource, date, timeSlot } });

            if (ok) {
                document.getElementById("successMessage").style.display = "block";
                setTimeout(() => { window.location.href = "mybookings.html"; }, 1500);
            } else {
                 if(result.message.includes("blocked")){
                   const blockedMsg = document.getElementById("blockedMessage");
                   if (blockedMsg) {
                       blockedMsg.style.display = "block";
                       setTimeout(() => blockedMsg.style.display = "none", 4000);
                   }
                 } else {
                    alert(result.message);
                 }
            }
        } catch(err) {
            console.error("Booking error:", err);
            alert("Could not connect to server.");
        }
    });
}
