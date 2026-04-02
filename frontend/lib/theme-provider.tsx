"use client";
import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({ theme: "light", setTheme: () => {} });

export function useTheme() { return useContext(ThemeContext); }

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");
  useEffect(() => {
    const stored = localStorage.getItem("junas-theme") as Theme | null;
    if (stored) { setThemeState(stored); apply(stored); }
  }, []);
  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem("junas-theme", t);
    apply(t);
  };
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}

function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}
