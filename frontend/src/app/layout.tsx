import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "NotebookAI — Your research workspace",
  description:
    "Your sources, connected. A personal workspace for reading and research.",
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
