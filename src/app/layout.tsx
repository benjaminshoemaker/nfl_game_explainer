import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NFL Game Explainer",
  description: "Live NFL game analysis with advanced stats and win probability tracking",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <main className="relative z-10 min-h-screen">
          {children}
        </main>
        <Analytics />
      </body>
    </html>
  );
}
