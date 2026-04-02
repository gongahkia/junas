"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import ThemeToggle from "./theme-toggle";

type NavItem = {
  href: string;
  label: string;
};

type NavSection = {
  heading: string;
  items: NavItem[];
};

const sections: NavSection[] = [
  {
    heading: "Search",
    items: [
      { href: "/", label: "Home" },
      { href: "/glossary", label: "Glossary" },
      { href: "/statutes", label: "Statutes" },
      { href: "/search", label: "Cases" },
      { href: "/research", label: "Research" },
      { href: "/legal-sources", label: "Legal Sources" },
    ],
  },
  {
    heading: "Analyze",
    items: [
      { href: "/contracts", label: "Contracts" },
      { href: "/ner", label: "NER" },
      { href: "/compliance", label: "Compliance" },
      { href: "/batch-analysis", label: "Batch Analysis" },
    ],
  },
  {
    heading: "Draft",
    items: [
      { href: "/chat", label: "AI Chat" },
      { href: "/clauses", label: "Clauses" },
      { href: "/templates", label: "Templates" },
    ],
  },
  {
    heading: "Predict",
    items: [{ href: "/predictions", label: "Court Outcomes" }],
  },
  {
    heading: "Evaluate",
    items: [{ href: "/benchmarks", label: "Benchmarks" }],
  },
  {
    heading: "Reference",
    items: [
      { href: "/rome-statute", label: "Rome Statute" },
      { href: "/compare-jurisdictions", label: "Compare" },
    ],
  },
  {
    heading: "System",
    items: [{ href: "/settings", label: "Settings" }],
  },
];

type SideNavProps = {
  apiBaseUrl: string;
};

export default function SideNav({ apiBaseUrl }: SideNavProps) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string): boolean => {
    if (href === "/") {
      return pathname === "/";
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="sidebar-header-row">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <h1 className="brand">Junas</h1>
          <ThemeToggle />
        </div>
        <button
          type="button"
          className="sidebar-toggle"
          onClick={() => setOpen((value) => !value)}
          aria-label="Toggle navigation"
        >
          Menu
        </button>
      </div>

      <nav>
        {sections.map((section) => (
          <section key={section.heading} className="nav-section">
            <h2 className="nav-heading">{section.heading}</h2>
            <ul className="nav-list">
              {section.items.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`nav-link ${isActive(item.href) ? "nav-link-active" : ""}`}
                    onClick={() => setOpen(false)}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>

      <p className="meta">API: {apiBaseUrl}</p>
    </aside>
  );
}
