import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { JunasProvider } from "@/lib/context/JunasContext";

const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});

export const metadata: Metadata = {
  title: "Junas",
  description: "Your AI legal assistant specialized in Singapore law. Get help with contract analysis, case law research, and legal document drafting.",
  keywords: ["legal", "AI", "Singapore", "law", "assistant", "contract", "case law"],
  authors: [{ name: "Junas Team" }],
  robots: "index, follow",
  icons: {
    icon: "/bishop.png",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}>
        <ErrorBoundary>
          <JunasProvider>
            {children}
          </JunasProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
