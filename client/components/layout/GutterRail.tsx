"use client";

import { useEffect, useState } from "react";

const SECTIONS = [
  { id: "section-01", num: "01", label: "Hero Trace" },
  { id: "section-02", num: "02", label: "Consequences" },
  { id: "section-03", num: "03", label: "Brain Strata" },
  { id: "section-04", num: "04", label: "Capabilities" },
  { id: "section-05", num: "05", label: "Walkthrough" },
  { id: "section-06", num: "06", label: "Local First" },
  { id: "section-07", num: "07", label: "Privacy Ledger" },
  { id: "section-08", num: "08", label: "Evaluation & CTA" },
];

export function GutterRail() {
  const [activeSection, setActiveSection] = useState("section-01");

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 200;
      for (const section of SECTIONS) {
        const el = document.getElementById(section.id);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveSection(section.id);
            break;
          }
        }
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      aria-label="Section Gutter Navigation"
      className="hidden xl:flex fixed left-6 top-1/2 -translate-y-1/2 flex-col gap-3 z-30 font-mono text-[11px]"
    >
      {SECTIONS.map((section) => {
        const isActive = activeSection === section.id;
        return (
          <a
            key={section.id}
            href={`#${section.id}`}
            title={section.label}
            className={`group flex items-center gap-2 py-1 px-1.5 transition-colors ${
              isActive ? "text-[var(--signal)]" : "text-[var(--fg-2)] hover:text-[var(--fg-0)]"
            }`}
          >
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full transition-transform ${
                isActive
                  ? "bg-[var(--signal)] scale-125"
                  : "bg-[var(--line-2)] group-hover:bg-[var(--fg-2)]"
              }`}
            />
            <span>{section.num}</span>
          </a>
        );
      })}
    </nav>
  );
}
