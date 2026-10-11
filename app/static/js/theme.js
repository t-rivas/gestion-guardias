const themeToggle = document.querySelector("[data-theme-toggle]");

function updateThemeToggle(theme) {
    const isDark = theme === "dark";
    const actionLabel = isDark ? "Activar modo claro" : "Activar modo nocturno";

    themeToggle.setAttribute("aria-pressed", String(isDark));
    themeToggle.setAttribute("aria-label", actionLabel);
    themeToggle.setAttribute("title", actionLabel);
}

if (themeToggle) {
    updateThemeToggle(document.documentElement.dataset.theme);

    themeToggle.addEventListener("click", () => {
        const currentTheme = document.documentElement.dataset.theme;
        const nextTheme = currentTheme === "dark" ? "light" : "dark";

        document.documentElement.dataset.theme = nextTheme;
        try {
            localStorage.setItem("guardias-theme", nextTheme);
        } catch (_) {}
        updateThemeToggle(nextTheme);
    });
}
