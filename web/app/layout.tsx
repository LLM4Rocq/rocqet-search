import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rocqet — Semantic search for Rocq",
  description: "Find theorems, lemmas and definitions across Rocq/Coq libraries using natural language.",
  openGraph: {
    title: "Rocqet",
    description: "Find theorems faster in Rocq/Coq",
    siteName: "Rocqet",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
