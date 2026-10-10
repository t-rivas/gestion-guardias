const availabilityForm = document.querySelector("[data-availability-form]");
if (availabilityForm) {
    const toggles = [...availabilityForm.querySelectorAll("[data-availability-toggle]")];
    const changes = new Map();
    const saveButton = availabilityForm.querySelector("[data-availability-save]");
    const status = availabilityForm.querySelector("[data-availability-status]");

    function updateState() {
        availabilityForm.querySelector("[data-availability-changes]").value = JSON.stringify([...changes.values()]);
        saveButton.disabled = changes.size === 0;
        status.textContent = changes.size ? `${changes.size} cambios pendientes de guardar.` : "Hacé los cambios necesarios y guardalos al finalizar.";
    }

    function setToggle(toggle, available) {
        toggle.dataset.available = String(available);
        toggle.classList.toggle("is-available", available);
        toggle.classList.toggle("is-unavailable", !available);
        toggle.textContent = available ? "✓" : "×";
        toggle.setAttribute("aria-pressed", String(available));
        toggle.setAttribute("aria-label", `${toggle.dataset.personName}: ${available ? "disponible" : "no disponible"} como ${toggle.dataset.roleLabel} el ${toggle.dataset.dayLabel}`);
        const key = `${toggle.dataset.personId}:${toggle.dataset.day}:${toggle.dataset.role}`;
        if (available === (toggle.dataset.originalAvailable === "true")) changes.delete(key);
        else changes.set(key, {
            person_id: Number(toggle.dataset.personId),
            day: toggle.dataset.day,
            role: toggle.dataset.role,
            available
        });
    }
    toggles.forEach(toggle => toggle.addEventListener("click", () => {
        setToggle(toggle, toggle.dataset.available !== "true");
        updateState();
    }));
    availabilityForm.querySelectorAll("[data-bulk-available]").forEach(button => button.addEventListener("click", () => {
        const person = availabilityForm.querySelector("[data-bulk-person]").value;
        const role = availabilityForm.querySelector("[data-bulk-role]").value;
        const start = availabilityForm.querySelector("[data-bulk-start]").value;
        const end = availabilityForm.querySelector("[data-bulk-end]").value;
        const weekday = availabilityForm.querySelector("[data-bulk-weekday]").value;
        if (!start || !end || start > end) {
            status.textContent = "Elegí un rango de fechas válido.";
            return;
        }
        toggles.forEach(toggle => {
            const day = (new Date(`${toggle.dataset.day}T12:00:00`).getDay() + 6) % 7;
            const matchesDay = weekday === "all" || (weekday === "weekdays" && day < 5) || (weekday === "weekends" && day >= 5) || Number(weekday) === day;
            if ((role === "both" || role === toggle.dataset.role) && (person === "all" || person === toggle.dataset.personId) && toggle.dataset.day >= start && toggle.dataset.day <= end && matchesDay) setToggle(toggle, button.dataset.bulkAvailable === "true");
        });
        updateState();
    }));

    function warn(event) {
        if (changes.size) {
            event.preventDefault();
            event.returnValue = "";
        }
    }
    window.addEventListener("beforeunload", warn);
    availabilityForm.addEventListener("submit", () => {
        window.removeEventListener("beforeunload", warn);
        saveButton.disabled = true;
        saveButton.textContent = "Guardando...";
    });
    updateState();
}
