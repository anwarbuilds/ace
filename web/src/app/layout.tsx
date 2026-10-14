import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { getPrefs } from "@/lib/prefs";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ace",
  description: "A private career engine.",
  icons: {
    icon: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%231F2628'/%3E%3Ctext x='16' y='22.5' text-anchor='middle' font-family='Arial,Helvetica,sans-serif' font-weight='700' font-size='19' fill='%23ECEFF1'%3Ea%3C/text%3E%3C/svg%3E",
  },
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // The theme is a cookie so the server writes it into the first byte of
  // HTML: no script, and no flash of the wrong theme. "system" leaves the
  // attribute off and lets the stylesheet follow the operating system.
  const { theme } = await getPrefs();
  return (
    <html
      lang="en"
      data-theme={theme === "system" ? undefined : theme}
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <body>{children}</body>
    </html>
  );
}
