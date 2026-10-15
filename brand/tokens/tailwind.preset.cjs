// Tailwind preset that reads the CSS variables in devmind-tokens.css (Tailwind v3-style config).
// For Tailwind v4, map the same variables inside an @theme block instead. [VERIFY at implementation]
module.exports = {
  theme: {
    extend: {
      colors: {
        bg: { 0: "var(--bg-0)", 1: "var(--bg-1)", 2: "var(--bg-2)" },
        line: { 1: "var(--line-1)", 2: "var(--line-2)", 3: "var(--line-3)" },
        fg: { 0: "var(--fg-0)", 1: "var(--fg-1)", 2: "var(--fg-2)" },
        signal: "var(--signal)", ref: "var(--ref)", warn: "var(--warn)", danger: "var(--danger)",
      },
      fontFamily: { display: "var(--font-display)", sans: "var(--font-ui)", mono: "var(--font-mono)" },
      borderRadius: { chip: "var(--radius-chip)", control: "var(--radius-control)", panel: "var(--radius-panel)" },
      transitionDuration: { 1: "var(--dur-1)", 2: "var(--dur-2)", 3: "var(--dur-3)", 4: "var(--dur-4)" },
      transitionTimingFunction: { out: "var(--ease-out)", in: "var(--ease-in)", move: "var(--ease-move)" },
    },
  },
};
