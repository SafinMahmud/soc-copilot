import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SOC Investigation Copilot",
  description: "AI-powered security investigation copilot for Splunk",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
