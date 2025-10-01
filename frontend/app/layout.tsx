import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI-Lona SaaS",
  description: "Control center for the AI-Lona trading bot"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
