import type { Metadata } from "next";
import "./globals.css";
import VisitPing from "./VisitPing";

const DESCRIPTION =
  "Find theorems, lemmas and definitions across Rocq/Coq libraries using natural language.";

export const metadata: Metadata = {
  metadataBase: new URL("https://rocqet.vercel.app"),
  title: "Rocqet — Semantic search for Rocq",
  description: DESCRIPTION,
  keywords: ["Rocq", "Coq", "MathComp", "theorem search", "semantic search", "formal verification"],
  openGraph: {
    title: "Rocqet",
    description: DESCRIPTION,
    siteName: "Rocqet",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Rocqet",
    description: DESCRIPTION,
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
      <body>
        <VisitPing />
        {children}
      </body>
    </html>
  );
}
