export type Theme = "light" | "dark";

const KEY = "limo-theme";

/** Stored choice, else the system preference (ADR-13). */
export function initialTheme(): Theme {
  const stored = localStorage.getItem(KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Sets the `dark` class on <html> and remembers the choice. */
export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem(KEY, theme);
}
