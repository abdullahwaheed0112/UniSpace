// home.js: the "Open today" snapshot on the home page, built from the public availability data.

(async function () {
    const list = document.getElementById("today-list");
    const note = document.getElementById("today-note");
    const legend = document.getElementById("today-legend");

    // Admins have no use for a "Request a booking" button
    if (Session.isLoggedIn && Session.role === "admin") {
        document.getElementById("home-actions").innerHTML =
            '<a class="btn btn-primary" href="dashboard.html">Open requests</a><a class="btn" href="resources.html">See availability</a>';
    }

    try {
        const meta = await loadMeta();
        const day = upcomingWeekdays(1)[0];
        const isToday = day === isoDate(new Date());
        document.getElementById("today-title").textContent = isToday ? "Open today" : "Next open day";
        note.textContent = formatDay(day) + (isToday ? "" : " (resources are open on weekdays)");

        const [availability, blocked] = await Promise.all([
            apiFetch(`/availability?from=${day}&to=${day}`, { auth: false }),
            apiFetch("/blocked_slots", { auth: false }),
        ]);
        const taken = Array.isArray(availability.data) ? availability.data : [];
        const blocks = Array.isArray(blocked.data) ? blocked.data : [];

        list.innerHTML = meta.resources.map((resource) => {
            const states = meta.slots.map((slot) => {
                let state = "free";
                if (blocks.some((b) => b.resource === resource && b.date === day && b.time === slot.value)) state = "blocked";
                else {
                    const hit = taken.find((t) => t.resource === resource && t.timeSlot === slot.value);
                    if (hit) state = hit.status === "Approved" ? "booked" : "requested";
                }
                return { slot, state };
            });
            const free = states.filter((s) => s.state === "free").length;
            const meter = states.map((s) => `<i data-state="${s.state}" title="${escapeHtml(s.slot.label)}: ${s.state}"></i>`).join("");
            return `<li><span class="name">${escapeHtml(resource)}</span>
                        <div class="meter" role="img" aria-label="${free} of ${states.length} slots free">${meter}</div>
                        <span class="muted mono">${free} of ${states.length} free</span></li>`;
        }).join("");
        legend.hidden = false;
    } catch (err) {
        list.innerHTML = '<li><span class="muted">Availability is not available right now. Is the server running?</span></li>';
    }
})();
