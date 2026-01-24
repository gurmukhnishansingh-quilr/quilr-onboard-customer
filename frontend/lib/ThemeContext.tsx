"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiFetch } from "./api";

export type Theme = "dark" | "light";

type ThemeContextType = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  loading: boolean;
};

type UserSettings = {
  theme: Theme;
};

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const THEME_STORAGE_KEY = "quilr-theme";

async function fetchUserSettings(): Promise<UserSettings | null> {
  try {
    const settings = await apiFetch<UserSettings>("/api/users/settings");
    return settings;
  } catch {
    return null;
  }
}

async function saveUserSettings(theme: Theme): Promise<void> {
  try {
    await apiFetch("/api/users/settings", {
      method: "PUT",
      json: { theme }
    });
  } catch {
    // Silently fail - localStorage is the fallback
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setMounted(true);

    // First apply localStorage theme immediately to avoid flash
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
    if (stored === "light" || stored === "dark") {
      setThemeState(stored);
      document.documentElement.setAttribute("data-theme", stored);
    }

    // Then try to fetch user settings from API
    fetchUserSettings().then((settings) => {
      if (settings && (settings.theme === "light" || settings.theme === "dark")) {
        setThemeState(settings.theme);
        document.documentElement.setAttribute("data-theme", settings.theme);
        localStorage.setItem(THEME_STORAGE_KEY, settings.theme);
      }
      setLoading(false);
    });
  }, []);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    document.documentElement.setAttribute("data-theme", newTheme);

    // Save to backend (fire and forget)
    void saveUserSettings(newTheme);
  };

  if (!mounted) {
    return <>{children}</>;
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, loading }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
