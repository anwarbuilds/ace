import type { Metadata } from "next";
import localFont from "next/font/local";

import { getPrefs } from "@/lib/prefs";

import "./globals.css";

// Next ships these Geist files with the installed package. Loading them
// locally keeps production and container builds independent of Google.
const geistSans = localFont({
  src: "../../node_modules/next/dist/next-devtools/server/font/geist-latin.woff2",
  variable: "--font-geist-sans",
  weight: "100 900",
  display: "swap",
});

const geistMono = localFont({
  src: "../../node_modules/next/dist/next-devtools/server/font/geist-mono-latin.woff2",
  variable: "--font-geist-mono",
  weight: "100 900",
  display: "swap",
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
