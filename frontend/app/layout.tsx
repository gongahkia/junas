import type { Metadata } from "next";
import SideNav from "../components/side-nav";
import { ThemeProvider } from "../lib/theme-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Junas",
  description: "Legal AI platform — multi-jurisdiction retrieval, AI chat, contract analysis, and more.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `try{if(localStorage.getItem("junas-theme")==="dark"||(!localStorage.getItem("junas-theme")&&window.matchMedia("(prefers-color-scheme:dark)").matches)){document.documentElement.classList.add("dark")}}catch(e){}` }} />
      </head>
      <body>
        <ThemeProvider>
          <div className="shell">
            <SideNav apiBaseUrl={apiBaseUrl} />
            <main className="content">{children}</main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
