import { useState } from "react";

import { Button } from "@/components/ui/button";
import { applyTheme, initialTheme, type Theme } from "@/lib/theme";

/** Header switch between light and dark; starts from the stored or system mode (ADR-13). */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => {
    const start = initialTheme();
    applyTheme(start);
    return start;
  });
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
    >
      {next === "dark" ? "Dark mode" : "Light mode"}
    </Button>
  );
}
