import { Suspense } from "react";
import type { Metadata, Viewport } from "next";
import { instrumentSerif, ibmPlexSans, jetbrainsMono } from "./fonts";
import { Header } from "../components/layout/Header";
import { GutterRail } from "../components/layout/GutterRail";
import { Footer } from "../components/layout/Footer";
import { AuthProvider } from "../components/auth/AuthProvider";
import { DevMindCursor } from "../components/cursor/DevMindCursor";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://devmind.warishlabs.in";

export const viewport: Viewport = {
  // eslint-disable-next-line no-restricted-syntax
  themeColor: "#0B0F12",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "DevMind — Continuous Project Brain for Agentic Software Engineering",
    template: "%s | DevMind",
  },
  description:
    "An agentic AI software engineering system with a shared, continuously synchronized mental model of your codebase. Evidence-grounded code intelligence, security analysis, and local-first companion.",
  keywords: [
    "DevMind",
    "Agentic Software Engineering",
    "Code Intelligence",
    "Project Brain",
    "AST Analysis",
    "Security Evidence E0-E3",
    "Blast Radius",
    "Local-First Code Companion",
    "VS Code Extension",
    "Developer Tools",
  ],
  authors: [{ name: "WarishLabs", url: "https://warishlabs.in" }],
  creator: "WarishLabs",
  publisher: "WarishLabs",
  applicationName: "DevMind",
  category: "technology",
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/site.webmanifest",
  openGraph: {
    title: "DevMind — Continuous Project Brain for Agentic Software Engineering",
    description:
      "Agentic AI software engineering system with shared Project Brain, evidence-grounded findings (E0-E3), and local-first companion.",
    url: siteUrl,
    siteName: "DevMind",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/og-image-1200x630.png",
        width: 1200,
        height: 630,
        alt: "DevMind — Continuous Project Brain",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "DevMind — Continuous Project Brain for Agentic Software Engineering",
    description:
      "Agentic AI software engineering system with shared Project Brain and local-first companion.",
    images: ["/og-image-1200x630.png"],
    creator: "@WarishLabs",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${siteUrl}/#website`,
      url: siteUrl,
      name: "DevMind",
      description:
        "Continuous Project Brain for Agentic Software Engineering. Evidence-grounded code intelligence and architectural blast radius analysis.",
      publisher: {
        "@id": `${siteUrl}/#organization`,
      },
    },
    {
      "@type": "Organization",
      "@id": `${siteUrl}/#organization`,
      name: "WarishLabs",
      url: siteUrl,
      logo: {
        "@type": "ImageObject",
        url: `${siteUrl}/favicon.svg`,
      },
    },
    {
      "@type": "SoftwareApplication",
      "@id": `${siteUrl}/#software`,
      name: "DevMind",
      applicationCategory: "DeveloperApplication",
      operatingSystem: "VS Code, Linux, macOS, Windows",
      description:
        "An agentic AI software engineering system with a shared, continuously synchronized mental model of your codebase. Evidence-grounded code intelligence, security analysis, and local-first companion.",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${instrumentSerif.variable} ${ibmPlexSans.variable} ${jetbrainsMono.variable} dark`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-screen flex flex-col bg-[var(--bg-0)] text-[var(--fg-0)] selection:bg-[var(--signal)] selection:text-[var(--bg-0)]">
        {/* Custom Evidence Node Cursor (Fine pointer desktop only) */}
        <DevMindCursor />

        {/* Accessible Skip Link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[var(--signal)] focus:text-[var(--bg-0)] focus:rounded-control font-mono text-xs"
        >
          Skip to main content
        </a>

        <AuthProvider>
          <Suspense fallback={null}>
            <Header />
            <GutterRail />
          </Suspense>

          <main id="main-content" className="flex-1 w-full">
            <Suspense fallback={null}>{children}</Suspense>
          </main>

          <Suspense fallback={null}>
            <Footer />
          </Suspense>
        </AuthProvider>
      </body>
    </html>
  );
}
