import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Find the story — pitch angle generator",
  description: "Paste an update. Get the angles a journalist would care about.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
