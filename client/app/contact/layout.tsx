import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact Us · DevMind & WarishLabs",
  description:
    "Contact the DevMind engineering team at WarishLabs for enterprise inquiries, architecture questions, security reports, or support.",
  alternates: {
    canonical: "/contact",
  },
};

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children;
}
