// mybookings.js: a student's bookings, their history, and cancelling.

(async function () {
    if (!Session.isLoggedIn) {
        window.location.href = "signin.html";
        return;
    }
    if (Session.role === "admin") {
        window.location.href = "dashboard.html";
        return;
    }

    const openList = document.getElementById("open-list");
    const closedList = document.getElementById("closed-list");
    const message = document.getElementById("message");

    let meta;
    try {
        meta = await loadMeta();
    } catch (err) {
        openList.innerHTML = closedList.innerHTML = '<p class="empty">Could not reach the server. Is it running?</p>';
        return;
    }
    const slotLabel = (code) => meta.slots.find((s) => s.value === code)?.label || code;
    const isOpen = (b) => ["Pending", "Under Review", "Approved"].includes(b.status);

    function row(b) {
        const note = b.note ? `<div class="muted" style="margin-top:4px;">Reason: ${escapeHtml(b.note)}</div>` : "";
        const cancel = isOpen(b) ? `<button type="button" class="btn btn-sm btn-danger" data-cancel="${b.id}">Cancel</button>` : "";
        return `<tr data-id="${b.id}">
            <td><strong>${escapeHtml(b.resource)}</strong></td>
            <td>${escapeHtml(formatDay(b.date))}</td>
            <td class="mono">${escapeHtml(slotLabel(b.timeSlot))}</td>
            <td>${statusChip(b.status)}${note}
                <details class="history" data-history="${b.id}"><summary>History</summary><div class="history-body muted">Loading…</div></details></td>
            <td><div class="actions">${cancel}</div></td>
        </tr>`;
    }

    function table(rows, emptyText) {
        if (rows.length === 0) return `<p class="empty">${escapeHtml(emptyText)}</p>`;
        return `<div class="table-wrap"><table class="table">
            <thead><tr><th>Resource</th><th>Date</th><th>Time</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
            <tbody>${rows.map(row).join("")}</tbody></table></div>`;
    }

    async function load() {
        const { ok, data } = await apiFetch("/bookings");
        if (!ok || !Array.isArray(data)) {
            openList.innerHTML = closedList.innerHTML = '<p class="empty">Could not load your bookings.</p>';
            return;
        }
        const open = data.filter(isOpen).sort((a, b) => (a.date + a.timeSlot).localeCompare(b.date + b.timeSlot));
        const closed = data.filter((b) => !isOpen(b)).sort((a, b) => b.date.localeCompare(a.date));
        openList.innerHTML = table(open, "You have no open requests. Use Book a space to make one.");
        closedList.innerHTML = table(closed, "Nothing here yet.");
    }

    // History is loaded when a booking's <details> is opened
    document.addEventListener("toggle", async (event) => {
        const details = event.target;
        if (!(details instanceof HTMLDetailsElement) || !details.open || !details.dataset.history) return;
        const body = details.querySelector(".history-body");
        const { ok, data } = await apiFetch(`/bookings/${details.dataset.history}`);
        if (!ok) { body.textContent = "Could not load the history."; return; }
        body.innerHTML = '<ol class="timeline">' + data.history.map((e) => {
            const who = e.actor === "system" ? "System" : e.actor;
            const what = e.fromStatus ? `${escapeHtml(e.fromStatus)} → ${escapeHtml(e.toStatus)}` : `Requested (${escapeHtml(e.toStatus)})`;
            return `<li><span class="when">${escapeHtml(e.at)}</span><br>${what} by ${escapeHtml(who)}${e.note ? `<br><span class="muted">${escapeHtml(e.note)}</span>` : ""}</li>`;
        }).join("") + "</ol>";
    }, true);

    document.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-cancel]");
        if (!button) return;
        const note = await askReason({
            title: "Cancel this booking?",
            message: "The slot becomes available to others again.",
            confirmLabel: "Cancel booking",
            required: false,
            danger: true,
        });
        if (note === null) return;
        const { ok, data } = await apiFetch(`/bookings/${button.dataset.cancel}/status`, { method: "PUT", body: { status: "Cancelled", note } });
        showNotice(message, ok ? "success" : "error", ok ? "Booking cancelled." : (data?.message || "Could not cancel the booking."));
        load();
    });

    load();
})();
