import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareSignal",
  description: "Multilingual hypertension follow-up for resource-constrained care settings.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

