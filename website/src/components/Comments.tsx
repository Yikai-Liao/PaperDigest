import Giscus, { type Theme } from "@giscus/react";
import { GISCUS } from "@/constants";
import { useEffect, useState } from "react";

interface CommentsProps {
  lightTheme?: Theme;
  darkTheme?: Theme;
}

export default function Comments({
  lightTheme = "light", // Default light theme for Giscus
  darkTheme = "dark",   // Default dark theme for Giscus
}: CommentsProps) {
  const [theme, setTheme] = useState(() => {
    if (typeof window === "undefined") return "light"; // Default theme during SSR
    // Check localStorage for theme first (set by Astro Paper's theme toggle)
    const currentTheme = localStorage.getItem("theme");
    // Fallback to browser preference if localStorage is not set
    const browserTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
    return currentTheme || browserTheme;
  });

  useEffect(() => {
    // Listener for localStorage theme changes (from Astro Paper toggle)
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === "theme" && event.newValue) {
        setTheme(event.newValue);
      }
    };

    // Listener for browser theme changes (system preference)
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleSystemThemeChange = ({ matches }: MediaQueryListEvent) => {
      // Only update if localStorage theme is not explicitly set
      if (!localStorage.getItem("theme")) {
        setTheme(matches ? "dark" : "light");
      }
    };

    window.addEventListener("storage", handleStorageChange);
    mediaQuery.addEventListener("change", handleSystemThemeChange);

    // Initial check in case the component mounts after the theme is set
    const initialTheme = localStorage.getItem("theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(initialTheme);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      mediaQuery.removeEventListener("change", handleSystemThemeChange);
    };
  }, []);

  // Determine which Giscus theme to use based on the current state
  const giscusTheme = theme === "light" ? lightTheme : darkTheme;

  return (
    <Giscus
      {...GISCUS} // Spread the config from constants.ts
      theme={giscusTheme} // Pass the dynamically determined theme
    />
  );
}
