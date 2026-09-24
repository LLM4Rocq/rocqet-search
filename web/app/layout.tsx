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

const THEME_INIT = `
(function () {
  try {
    var stored = localStorage.getItem("rocqet-theme");
    var dark = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (dark) document.documentElement.classList.add("dark");
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
