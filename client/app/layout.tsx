import type { Metadata } from "next";
import { instrumentSerif, ibmPlexSans, jetbrainsMono } from "./fonts";
import { Header } from "../components/layout/Header";
import { GutterRail } from "../components/layout/GutterRail";
import { Footer } from "../components/layout/Footer";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://devmind.warishlabs.in";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "DevMind — Continuous Project Brain for Agentic Software Engineering",
  description:
    "An agentic AI software engineering system with a shared, continuously synchronized mental model of your codebase. Evidence-grounded code intelligence, security analysis, and local-first companion.",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/site.webmanifest",
  openGraph: {
    title: "DevMind — Continuous Project Brain",
    description:
      "Agentic AI software engineering system with shared Project Brain, evidence-grounded findings (E0-E3), and local-first companion.",
    url: siteUrl,
    siteName: "DevMind",
    type: "website",
    images: [
      {
        url: "
import type { Metadata } from "next";

export const metadata: Metadata = {
  metadataBase: new URL("https://devmind.warishlabs.in"),

  title: "DevMind | AI-Powered Developer Tools",
  description:
    "Explore DevMind, your toolkit for smarter development and productivity.",

  openGraph: {
    title: "DevMind | AI-Powered Developer Tools",
    description:
      "Explore DevMind, your toolkit for smarter development and productivity.",
    url: "https://devmind.warishlabs.in",
    siteName: "DevMind",
    type: "website",
    images: [
      {
        url: "/og-image-1200x630.png",
        width: 1200,
        height: 630,
        alt: "DevMind — AI-Powered Developer Tools",
      },
    ],
  },

  twitter: {
    card: "summary_large_image",
    title: "DevMind | AI-Powered Developer Tools",
    description:
      "Explore DevMind, your toolkit for smarter development and productivity.",
    images: ["/og-image-1200x630.png"],
  },
};
",
        width: 1200,
        height: 630,
        alt: "DevMind — Continuous Project Brain",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "DevMind — Continuous Project Brain",
    description:
      "Agentic AI software engineering system with shared Project Brain and local-first companion.",
    images: ["/og-image-1200x630.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${instrumentSerif.variable} ${ibmPlexSans.variable} ${jetbrainsMono.variable} dark`}
    >
      <body className="min-h-screen flex flex-col bg-[var(--bg-0)] text-[var(--fg-0)] selection:bg-[var(--signal)] selection:text-[var(--bg-0)]">
        {/* Accessible Skip Link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[var(--signal)] focus:text-[var(--bg-0)] focus:rounded-control font-mono text-xs"
        >
          Skip to main content
        </a>

        <Header />
        <GutterRail />

        <main id="main-content" className="flex-1 w-full">
          {children}
        </main>

        <Footer />
      </body>
    </html>
  );
}
