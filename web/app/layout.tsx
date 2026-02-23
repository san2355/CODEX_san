import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Hospital EMR Dashboard",
  description: "High-end hospital-grade RPM EMR interface"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
