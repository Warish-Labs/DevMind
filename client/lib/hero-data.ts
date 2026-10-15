/**
 * DevMind Hero Data Specification
 * Source of truth: docs/08-ui-ux-design-specification.md §8 and common/data/rule-catalog.json
 */

export interface HeroCodeToken {
  text: string;
  tone?: "keyword" | "ident" | "string" | "punct" | "comment";
}

export interface HeroCodeLine {
  lineNumber: number;
  tokens: HeroCodeToken[];
  isTarget?: boolean;
}

export const HERO_RULE_ID = "devmind.authz.missing_role_check" as const;

export const HERO_CODE_LINES: HeroCodeLine[] = [
  {
    lineNumber: 1,
    tokens: [
      { text: "import", tone: "keyword" },
      { text: " { ", tone: "punct" },
      { text: "Router", tone: "ident" },
      { text: " } ", tone: "punct" },
      { text: "from", tone: "keyword" },
      { text: ' "express"', tone: "string" },
      { text: ";", tone: "punct" },
    ],
  },
  {
    lineNumber: 2,
    tokens: [
      { text: "import", tone: "keyword" },
      { text: " { ", tone: "punct" },
      { text: "requireAuth", tone: "ident" },
      { text: " } ", tone: "punct" },
      { text: "from", tone: "keyword" },
      { text: ' "../auth"', tone: "string" },
      { text: ";", tone: "punct" },
    ],
  },
  {
    lineNumber: 3,
    tokens: [
      { text: "import", tone: "keyword" },
      { text: " { ", tone: "punct" },
      { text: "listUsers", tone: "ident" },
      { text: ", ", tone: "punct" },
      { text: "deleteUser", tone: "ident" },
      { text: " } ", tone: "punct" },
      { text: "from", tone: "keyword" },
      { text: ' "./users"', tone: "string" },
      { text: ";", tone: "punct" },
    ],
  },
  {
    lineNumber: 4,
    tokens: [],
  },
  {
    lineNumber: 5,
    tokens: [
      { text: "const", tone: "keyword" },
      { text: " router = ", tone: "punct" },
      { text: "Router", tone: "ident" },
      { text: "();", tone: "punct" },
    ],
  },
  {
    lineNumber: 6,
    tokens: [],
  },
  {
    lineNumber: 7,
    isTarget: true,
    tokens: [
      { text: "router.", tone: "punct" },
      { text: "get", tone: "ident" },
      { text: '("', tone: "punct" },
      { text: "/admin/users", tone: "string" },
      { text: '", ', tone: "punct" },
      { text: "requireAuth", tone: "ident" },
      { text: ", ", tone: "punct" },
      { text: "listUsers", tone: "ident" },
      { text: ");", tone: "punct" },
    ],
  },
  {
    lineNumber: 8,
    tokens: [
      { text: "router.", tone: "punct" },
      { text: "delete", tone: "ident" },
      { text: '("', tone: "punct" },
      { text: "/admin/users/:id", tone: "string" },
      { text: '", ', tone: "punct" },
      { text: "requireAuth", tone: "ident" },
      { text: ", ", tone: "punct" },
      { text: "requireRole", tone: "ident" },
      { text: '("', tone: "punct" },
      { text: "admin", tone: "string" },
      { text: '"), ', tone: "punct" },
      { text: "deleteUser", tone: "ident" },
      { text: ");", tone: "punct" },
    ],
  },
];

export interface RippleTagData {
  id: "review" | "docs" | "pr";
  label: string;
  peek: string;
}

export const HERO_RIPPLE_TAGS: RippleTagData[] = [
  {
    id: "review",
    label: "Review · add finding",
    peek: "Flagged for security review in current sprint backlog.",
  },
  {
    id: "docs",
    label: "Docs · no entry for /admin/users",
    peek: "Living documentation updated: endpoint missing OpenAPI documentation.",
  },
  {
    id: "pr",
    label: "Pull request · risk: high",
    peek: "PR check gate flagged: unauthenticated or unauthorized endpoint exposure.",
  },
];

export const HERO_MARGIN_NOTE = {
  header: "@@ /admin/users @@",
  authnLabel: "Authentication",
  authnStatus: "required",
  authnDetail: "requireAuth · auth.ts:12",
  authzLabel: "Authorization",
  authzStatus: "missing",
  authzDetail: "no role check on route or handler",
  evidenceLabel: "Evidence",
  evidenceLevel: "E1 · Possible",
  ruleId: HERO_RULE_ID,
  ruleDescription:
    "Sensitive administrative operation has authentication verified but lacks role or permission authorization validation.",
} as const;
