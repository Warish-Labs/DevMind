import { Hero } from "../components/hero/Hero";
import { Section02BlastRadius } from "../components/sections/Section02BlastRadius";
import { Section03BrainStrata } from "../components/sections/Section03BrainStrata";
import { Section04Capabilities } from "../components/sections/Section04Capabilities";
import { Section05Walkthrough } from "../components/sections/Section05Walkthrough";
import { Section06Diptych } from "../components/sections/Section06Diptych";
import { Section07PrivacyLedger } from "../components/sections/Section07PrivacyLedger";
import { Section08CTA } from "../components/sections/Section08CTA";
import { HomepageHealthTrigger } from "../components/health/HomepageHealthTrigger";

export default function HomePage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex flex-col gap-28">
      {/* 00: Non-blocking liveness probe trigger (throttled 1h) */}
      <HomepageHealthTrigger />

      {/* 01: Hero Trace Section */}
      <Hero />

      {/* 02: One Change / Five Consequences */}
      <Section02BlastRadius />

      {/* 03: Project Brain Strata */}
      <Section03BrainStrata />

      {/* 04: Capability Index */}
      <Section04Capabilities />

      {/* 05: Walkthrough Sticky Timeline */}
      <Section05Walkthrough />

      {/* 06: Local-First Diptych */}
      <Section06Diptych />

      {/* 07: Privacy Ledger */}
      <Section07PrivacyLedger />

      {/* 08: CTA & In-App Preferences */}
      <Section08CTA />
    </div>
  );
}
