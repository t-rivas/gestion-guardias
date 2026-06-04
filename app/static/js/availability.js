const availabilityForm = document.querySelector("[data-availability-form]");

if (availabilityForm) {
    const changesInput = availabilityForm.querySelector("[data-availability-changes]");
    const saveButton = availabilityForm.querySelector("[data-availability-save]");
    const statusText = availabilityForm.querySelector("[data-availability-status]");
    const toggles = availabilityForm.querySelectorAll("[data-availability-toggle]");
    const changes = new Map();

    function updateSaveState() {
        const pendingCount = changes.size;

        changesInput.value = JSON.stringify(Array.from(changes.values()));
        saveButton.disabled = pendingCount === 0;
        statusText.textContent = pendingCount === 0
            ? "Hacé los cambios necesarios y guardalos al finalizar."
            : `${pendingCount} ${pendingCount === 1 ? "cambio pendiente" : "cambios pendientes"} de guardar.`;
    }

    function updateToggle(toggle, isAvailable) {
        toggle.dataset.available = String(isAvailable);
        toggle.classList.toggle("is-available", isAvailable);
        toggle.classList.toggle("is-unavailable", !isAvailable);
        toggle.textContent = isAvailable ? "✓" : "×";
        toggle.setAttribute(
            "aria-label",
            `${toggle.dataset.personName}: ${isAvailable ? "disponible" : "no disponible"} el ${toggle.dataset.dayLabel}`,
        );
    }

    toggles.forEach((toggle) => {
        toggle.addEventListener("click", () => {
            const isAvailable = toggle.dataset.available === "true";
            const nextAvailable = !isAvailable;
            const originalAvailable = toggle.dataset.originalAvailable === "true";
            const key = `${toggle.dataset.personId}:${toggle.dataset.day}`;

            updateToggle(toggle, nextAvailable);

            if (nextAvailable === originalAvailable) {
                changes.delete(key);
            } else {
                changes.set(key, {
                    person_id: Number(toggle.dataset.personId),
                    day: toggle.dataset.day,
                    available: nextAvailable,
                });
            }

            updateSaveState();
        });
    });

    availabilityForm.addEventListener("submit", () => {
        window.removeEventListener("beforeunload", warnAboutUnsavedChanges);
        saveButton.disabled = true;
        saveButton.textContent = "Guardando...";
    });

    function warnAboutUnsavedChanges(event) {
        if (changes.size === 0) {
            return;
        }

        event.preventDefault();
        event.returnValue = "";
    }

    window.addEventListener("beforeunload", warnAboutUnsavedChanges);
    updateSaveState();
}
