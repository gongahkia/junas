import type { Metadata } from "next";
import { IBM_Plex_Serif } from "next/font/google";
import "./globals.css";

const ibmPlexSerif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-plex-serif",
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
      <body className={`${ibmPlexSerif.variable} font-serif antialiased`}>
        {children}
      </body>
    </html>
  );
}
