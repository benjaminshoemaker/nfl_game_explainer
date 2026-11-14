import type { Metadata } from "next";
import "./globals.css";
import localFont from 'next/font/local';

const publicSans = localFont({
  src: [
    { path: './fonts/public-sans-regular.ttf', weight: '400', style: 'normal' },
    { path: './fonts/public-sans-semibold.ttf', weight: '600', style: 'normal' },
    { path: './fonts/public-sans-extrabold.ttf', weight: '800', style: 'normal' },
  ],
  variable: '--font-public-sans', display: 'swap', fallback: ['Arial'],
});
const sourceSerif = localFont({
  src: './fonts/source-serif-bold.ttf', weight: '700', style: 'normal',
  variable: '--font-source-serif', display: 'swap', fallback: ['Georgia'],
});

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
    <html lang="en" className={`${publicSans.variable} ${sourceSerif.variable}`}>
      <body className="antialiased">
        <main className="relative z-10 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
