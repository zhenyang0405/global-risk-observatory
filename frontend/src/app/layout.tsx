import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Global Risk Observatory",
  description: "Live world-risk Earth viz · Gemma 4 E4B + 26B A4B",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
