// booking.js: the booking request form (students only).

(async function () {
    const form = document.getElementById("bookingForm");
    const message = document.getElementById("message");
    const resourceSelect = document.getElementById("resource");
    const dateSelect = document.getElementById("date");
    const slotSelect = document.getElementById("timeSlot");
    const slotHelp = document.getElementById("slot-help");
    const submit = document.getElementById("submit");

    if (!Session.isLoggedIn) {
        window.location.href = "signin.html";
        return;
    }
    if (Session.role === "admin") {
        form.hidden = true;
        form.insertAdjacentHTML("afterend", '<div class="notice">Administrators review bookings but do not make them. Use the Requests page.</div>');
        return;
    }

    let meta;
    try {
        meta = await loadMeta();
    } catch (err) {
        showNotice(message, "error", "Could not reach the server. Is it running?");
        return;
    }

    const params = new URLSearchParams(location.search);
    resourceSelect.innerHTML = meta.resources.map((r) => `<option value="${escapeHtml(r)}">${escapeHtml(r)}</option>`).join("");
    if (meta.resources.includes(params.get("resource"))) resourceSelect.value = params.get("resource");

    const days = upcomingWeekdays(meta.bookingWindowDays);
    const today = isoDate(new Date());
    dateSelect.innerHTML = days.map((d) => `<option value="${d}">${escapeHtml(formatLongDay(d))}${d === today ? " (today)" : ""}</option>`).join("");
    if (days.includes(params.get("date"))) dateSelect.value = params.get("date");

    // Rebuild the slot list for the chosen resource and date: slots that have started, are booked or are blocked are disabled
    async function refreshSlots(preferred) {
        const resource = resourceSelect.value;
        const day = dateSelect.value;
        const [availability, blocked] = await Promise.all([
            apiFetch(`/availability?resource=${encodeURIComponent(resource)}&from=${day}&to=${day}`, { auth: false }),
            apiFetch("/blocked_slots", { auth: false }),
        ]);
        const taken = Array.isArray(availability.data) ? availability.data : [];
        const blocks = Array.isArray(blocked.data) ? blocked.data : [];
        const now = new Date();

        slotSelect.innerHTML = meta.slots.map((slot) => {
            let suffix = "";
            let disabled = false;
            if (day === today && slot.startHour <= now.getHours()) { suffix = " (already started)"; disabled = true; }
            else if (blocks.some((b) => b.resource === resource && b.date === day && b.time === slot.value)) { suffix = " (blocked)"; disabled = true; }
            else {
                const hit = taken.find((t) => t.timeSlot === slot.value);
                if (hit && hit.status === "Approved") { suffix = " (booked)"; disabled = true; }
                else if (hit) suffix = " (requested)";
            }
            return `<option value="${escapeHtml(slot.value)}"${disabled ? " disabled" : ""}>${escapeHtml(slot.label)}${suffix}</option>`;
        }).join("");

        const wanted = preferred || slotSelect.value;
        const option = [...slotSelect.options].find((o) => o.value === wanted && !o.disabled);
        slotSelect.value = option ? option.value : ([...slotSelect.options].find((o) => !o.disabled)?.value || "");
        updateHelp();
    }

    function updateHelp() {
        const option = slotSelect.selectedOptions[0];
        slotHelp.textContent = option && option.textContent.includes("(requested)")
            ? "Someone else has already asked for this slot. You can still request it; an administrator decides between requests."
            : "";
        submit.disabled = !slotSelect.value;
    }

    resourceSelect.addEventListener("change", () => refreshSlots());
    dateSelect.addEventListener("change", () => refreshSlots());
    slotSelect.addEventListener("change", updateHelp);
    await refreshSlots(params.get("slot"));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        submit.disabled = true;
        try {
            const { ok, data } = await apiFetch("/bookings", {
                method: "POST",
                body: { resource: resourceSelect.value, date: dateSelect.value, timeSlot: slotSelect.value },
            });
            if (ok) {
                showNotice(message, "success", "Request sent. You can follow it under My bookings.");
                setTimeout(() => { window.location.href = "mybookings.html"; }, 1200);
            } else {
                showNotice(message, "error", data?.message || "The request could not be sent.");
                submit.disabled = false;
                refreshSlots(slotSelect.value);
            }
        } catch (err) {
            showNotice(message, "error", "Could not reach the server. Is it running?");
            submit.disabled = false;
        }
    });
})();
