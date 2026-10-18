/**
 * Clerk theme appearance object matching DevMind design tokens (docs/08 §3, §4, §11 S-02).
 */

export const devmindClerkAppearance = {
  variables: {
    colorPrimary: "var(--signal)",
    colorBackground: "var(--bg-1)",
    colorText: "var(--fg-0)",
    colorTextSecondary: "var(--fg-1)",
    colorInputBackground: "var(--bg-2)",
    colorInputText: "var(--fg-0)",
    colorNeutral: "var(--fg-2)",
    borderRadius: "var(--radius-control)",
    fontFamily: "var(--font-ui)",
  },
  elements: {
    rootBox: "w-full flex justify-center",
    card: "bg-[var(--bg-1)] border border-[var(--line-2)] rounded-[var(--radius-panel)] shadow-2xl p-6",
    headerTitle: "text-[var(--fg-0)] font-sans font-semibold text-lg tracking-tight",
    headerSubtitle: "text-[var(--fg-2)] text-sm",
    socialButtonsBlockButton:
      "border border-[var(--line-3)] bg-[var(--bg-2)] hover:bg-[var(--bg-1)] text-[var(--fg-0)] rounded-[var(--radius-control)] transition-colors",
    formButtonPrimary:
      "bg-[var(--signal)] text-[var(--bg-0)] font-semibold rounded-[var(--radius-control)] hover:brightness-110 active:brightness-95 transition-all shadow-sm",
    formFieldInput:
      "bg-[var(--bg-2)] border border-[var(--line-3)] text-[var(--fg-0)] rounded-[var(--radius-control)] focus:border-[var(--ref)] focus:ring-1 focus:ring-[var(--ref)]",
    formFieldLabel: "text-[var(--fg-1)] text-xs font-medium",
    footerActionLink: "text-[var(--signal)] hover:underline",
    identityPreviewText: "text-[var(--fg-0)] font-mono text-xs",
    identityPreviewEditButton: "text-[var(--signal)] hover:underline",
    dividerLine: "bg-[var(--line-1)]",
    dividerText: "text-[var(--fg-2)] text-xs uppercase tracking-wider",
  },
};
