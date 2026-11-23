// dashboard.js: the administrator's request queue and maintenance blocks.

(async function () {
    if (!Session.isLoggedIn) {
        window.location.href = "signin.html";
        return;
    }
    if (Session.role !== "admin") {
        window.location.href = "index.html";
        return;
    }

    const queue = document.getElementById("queue");
    const filter = document.getElementById("filter");
    const glance = document.getElementById("glance");
    const message = document.getElementById("message");
    const blockForm = document.getElementById("blockForm");
    const blocked = document.getElementById("blocked");

    let meta;
    try {
        meta = await loadMeta();
    } catch (err) {
        queue.innerHTML = '<p class="empty">Could not reach the server. Is it running?</p>';
        return;
    }
    const slotLabel = (code) => meta.slots.find((s) => s.value === code)?.label || code;

    // ---- request queue ----
    const FILTERS = [
        { key: "Pending", label: "New", statuses: ["Pending"] },
        { key: "Review", label: "In review", statuses: ["Under Review"] },
        { key: "Approved", label: "Approved", statuses: ["Approved"] },
        { key: "Closed", label: "Closed", statuses: ["Rejected", "Cancelled"] },
        { key: "All", label: "All", statuses: null },
    ];
    let bookings = [];
    let active = "Pending";

    function actionsFor(b) {
        const button = (action, label, cls = "") => `<button type="button" class="btn btn-sm ${cls}" data-action="${action}" data-id="${b.id}">${label}</button>`;
        if (b.status === "Pending") return button("review", "Start review", "btn-primary") + button("reject", "Reject", "btn-danger");
        if (b.status === "Under Review") return button("approve", "Approve", "btn-primary") + button("reject", "Reject", "btn-danger");
        if (b.status === "Approved") return button("cancel", "Cancel", "btn-danger");
        return "";
    }

    function renderFilter() {
        filter.innerHTML = FILTERS.map((f) => {
            const n = f.statuses ? bookings.filter((b) => f.statuses.includes(b.status)).length : bookings.length;
            return `<button type="button" data-filter="${f.key}" aria-pressed="${f.key === active}">${escapeHtml(f.label)} <span class="mono">${n}</span></button>`;
        }).join("");
    }

    function renderQueue() {
        const f = FILTERS.find((x) => x.key === active);
        const rows = bookings
            .filter((b) => !f.statuses || f.statuses.includes(b.status))
            .sort((a, b) => (a.date + a.timeSlot).localeCompare(b.date + b.timeSlot));
        if (rows.length === 0) {
            queue.innerHTML = `<p class="empty">${active === "Pending" ? "No new requests. Nice and quiet." : "Nothing in this view."}</p>`;
            return;
        }
        queue.innerHTML = `<div class="table-wrap"><table class="table">
            <thead><tr><th>Request</th><th>When</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
            <tbody>${rows.map((b) => `<tr>
                <td><strong>${escapeHtml(b.resource)}</strong><div class="muted">${escapeHtml(b.username)}</div></td>
                <td>${escapeHtml(formatDay(b.date))}<div class="mono muted">${escapeHtml(slotLabel(b.timeSlot))}</div></td>
                <td>${statusChip(b.status)}${b.note ? `<div class="muted" style="margin-top:4px;">${escapeHtml(b.note)}</div>` : ""}</td>
                <td><div class="actions">${actionsFor(b)}</div></td></tr>`).join("")}</tbody></table></div>`;
    }

    function renderGlance() {
        const count = (s) => bookings.filter((b) => b.status === s).length;
        glance.innerHTML = ["Pending", "Under Review", "Approved", "Rejected", "Cancelled"].map((s) =>
            `<div class="row between"><dt>${statusChip(s)}</dt><dd class="mono" style="margin:0">${count(s)}</dd></div>`).join("");
    }

    async function loadBookings() {
        const { ok, data } = await apiFetch("/bookings");
        if (!ok || !Array.isArray(data)) {
            queue.innerHTML = '<p class="empty">Could not load requests.</p>';
            return;
        }
        bookings = data;
        renderFilter();
        renderQueue();
        renderGlance();
    }

    filter.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-filter]");
        if (!button) return;
        active = button.dataset.filter;
        renderFilter();
        renderQueue();
    });

    queue.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        const id = button.dataset.id;
        const booking = bookings.find((b) => String(b.id) === id);
        const action = button.dataset.action;
        let status;
        let note;

        if (action === "review") status = "Under Review";
        else if (action === "approve") status = "Approved";
        else {
            status = action === "reject" ? "Rejected" : "Cancelled";
            note = await askReason({
                title: action === "reject" ? "Reject this request?" : "Cancel this approved booking?",
                message: `${booking.resource}, ${formatDay(booking.date)}, ${slotLabel(booking.timeSlot)} (${booking.username}). The student sees this reason.`,
                confirmLabel: action === "reject" ? "Reject request" : "Cancel booking",
                required: true,
                danger: true,
            });
            if (note === null) return;
        }

        button.disabled = true;
        const { ok, data } = await apiFetch(`/bookings/${id}/status`, { method: "PUT", body: { status, note } });
        if (ok) {
            const extra = data.alsoRejected ? ` ${data.alsoRejected} competing request${data.alsoRejected > 1 ? "s were" : " was"} rejected automatically.` : "";
            showNotice(message, "success", `Now ${status}.${extra}`);
        } else {
            showNotice(message, "error", data?.message || "That change could not be made.");
        }
        loadBookings();
    });

    // ---- maintenance blocks ----
    document.getElementById("blockResource").innerHTML = meta.resources.map((r) => `<option>${escapeHtml(r)}</option>`).join("");
    document.getElementById("blockTime").innerHTML = meta.slots.map((s) => `<option value="${escapeHtml(s.value)}">${escapeHtml(s.label)}</option>`).join("");
    document.getElementById("blockDate").min = isoDate(new Date());

    async function loadBlocks() {
        const { data } = await apiFetch("/blocked_slots", { auth: false });
        const list = Array.isArray(data) ? data : [];
        blocked.innerHTML = list.length === 0 ? '<p class="muted">No slots are blocked.</p>' :
            "<ul style='list-style:none;margin:0;padding:0;display:grid;gap:8px'>" + list.map((b) =>
                `<li class="row between"><span><strong>${escapeHtml(b.resource)}</strong><br><span class="mono muted">${escapeHtml(formatDay(b.date))}, ${escapeHtml(slotLabel(b.time))}</span></span>
                 <button type="button" class="btn btn-sm" data-unblock="${escapeHtml(b.id)}">Unblock</button></li>`).join("") + "</ul>";
    }

    blockForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const body = {
            resource: document.getElementById("blockResource").value,
            date: document.getElementById("blockDate").value,
            time: document.getElementById("blockTime").value,
        };
        const { ok, data } = await apiFetch("/blocked_slots", { method: "POST", body });
        if (ok) {
            const n = data.affectedBookings || 0;
            showNotice(message, "success", `Slot blocked.${n ? ` ${n} booking${n > 1 ? "s were" : " was"} rejected or cancelled and the student${n > 1 ? "s were" : " was"} notified.` : ""}`);
            blockForm.reset();
            document.getElementById("blockDate").min = isoDate(new Date());
        } else {
            showNotice(message, "error", data?.message || "Could not block that slot.");
        }
        loadBlocks();
        loadBookings();
    });

    blocked.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-unblock]");
        if (!button) return;
        const { ok, data } = await apiFetch(`/blocked_slots/${button.dataset.unblock}`, { method: "DELETE" });
        showNotice(message, ok ? "success" : "error", ok ? "Slot unblocked." : (data?.message || "Could not unblock that slot."));
        loadBlocks();
    });

    loadBookings();
    loadBlocks();
})();
