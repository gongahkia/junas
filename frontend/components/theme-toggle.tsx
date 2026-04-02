"use client";
import { useTheme } from "../lib/theme-provider";

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button type="button" onClick={() => setTheme(next)} aria-label={`Switch to ${next} mode`}
      style={{ background: "none", border: "1px solid #94a3b8", borderRadius: "0.5rem", padding: "0.25rem 0.4rem", cursor: "pointer", fontSize: "0.85rem", lineHeight: 1 }}>
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}
