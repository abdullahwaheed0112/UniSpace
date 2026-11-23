// resources.js: the seven-day availability grid for one resource at a time.

(async function () {
    const picker = document.getElementById("resource-picker");
    const grid = document.getElementById("grid");
    const hint = document.getElementById("grid-hint");
    const caption = document.getElementById("grid-caption");

    const canBook = Session.isLoggedIn && Session.role === "student";
    hint.textContent = canBook ? "Select a free or requested slot to start a booking request."
        : Session.isLoggedIn ? "Administrators review requests from the Requests page."
        : "Sign in with a student account to request a booking.";

    let meta;
    try {
        meta = await loadMeta();
    } catch (err) {
        grid.querySelector("tbody").innerHTML = '<tr><td class="empty" colspan="6">Could not reach the server. Is it running?</td></tr>';
        return;
    }

    const params = new URLSearchParams(location.search);
    let current = meta.resources.includes(params.get("resource")) ? params.get("resource") : meta.resources[0];

    picker.innerHTML = meta.resources.map((r) => `<button type="button" data-resource="${escapeHtml(r)}" aria-pressed="false">${escapeHtml(r)}</button>`).join("");
    picker.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-resource]");
        if (!button) return;
        current = button.dataset.resource;
        render();
    });

    async function render() {
        picker.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.resource === current)));
        caption.textContent = `${current}: availability for the next seven days`;

        const days = upcomingWeekdays(meta.bookingWindowDays);
        const [availability, blocked] = await Promise.all([
            apiFetch(`/availability?resource=${encodeURIComponent(current)}&from=${days[0]}&to=${days[days.length - 1]}`, { auth: false }),
            apiFetch("/blocked_slots", { auth: false }),
        ]);
        const taken = Array.isArray(availability.data) ? availability.data : [];
        const blocks = (Array.isArray(blocked.data) ? blocked.data : []).filter((b) => b.resource === current);

        grid.querySelector("thead").innerHTML =
            "<tr><th scope='col'><span class='sr-only'>Time</span></th>" + days.map((d) => `<th scope="col">${escapeHtml(formatDay(d))}</th>`).join("") + "</tr>";

        const now = new Date();
        const today = isoDate(now);
        grid.querySelector("tbody").innerHTML = meta.slots.map((slot) => {
            const cells = days.map((day) => {
                if (day === today && slot.startHour <= now.getHours()) return '<td><span class="cell cell-past">Past</span></td>';
                if (blocks.some((b) => b.date === day && b.time === slot.value)) return '<td><span class="cell cell-blocked">Blocked</span></td>';
                const hit = taken.find((t) => t.date === day && t.timeSlot === slot.value);
                if (hit && hit.status === "Approved") return '<td><span class="cell cell-booked">Booked</span></td>';
                const kind = hit ? "requested" : "free";
                const label = hit ? "Requested" : "Free";
                if (canBook) {
                    const url = `booking.html?resource=${encodeURIComponent(current)}&date=${encodeURIComponent(day)}&slot=${encodeURIComponent(slot.value)}`;
                    return `<td><a class="cell cell-${kind}" href="${url}">${label}</a></td>`;
                }
                return `<td><span class="cell cell-${kind}">${label}</span></td>`;
            }).join("");
            return `<tr><th scope="row">${escapeHtml(slot.label)}</th>${cells}</tr>`;
        }).join("");
    }

    render();
})();
