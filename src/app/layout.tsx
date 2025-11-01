import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
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
      <body className={`${inter.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
