/**
 * DevMind Secret Detection and Redaction Pipeline (docs/07 §6, docs/06 §12).
 *
 * Scans and deterministically masks sensitive credentials, tokens, private keys,
 * and connection strings into the format: [REDACTED:<type>:<hash8>].
 * Fail-closed: Never returns unredacted sensitive values into logs, cloud diffs, or snippets.
 */

import { computeRedactedTokenHash } from "./hasher";

export interface RedactionResult {
  redactedText: string;
  redactionCount: number;
  countsByType: Record<string, number>;
}

interface RedactionRule {
  type: string;
  pattern: RegExp;
  apply: (
    match: string,
    ...groups: string[]
  ) => { replaced: string; redacted: boolean; secret: string };
}

const REDACTION_RULES: RedactionRule[] = [
  // 1. Private Keys (entire block or header)
  {
    type: "private_key",
    pattern:
      /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:private_key:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "private_key",
    pattern: /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[^\r\n]*/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:private_key:${hash8}]`, redacted: true, secret: match };
    },
  },

  // 2. Known API Keys & Cloud Credentials
  {
    type: "api_key",
    pattern: /\b(sk-ant-[A-Za-z0-9\-_]{32,})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:api_key:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "api_key",
    pattern: /\b(sk-[A-Za-z0-9]{32,})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:api_key:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "api_key",
    pattern: /\b(sk_live_[0-9a-zA-Z]{24,})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:api_key:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "api_key",
    pattern: /\b(sk_test_[0-9a-zA-Z]{24,})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:api_key:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "api_key",
    pattern: /\b(ghp_[0-9a-zA-Z]{36})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:api_key:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "api_key",
    pattern: /\b(github_pat_[0-9a-zA-Z_]{60,})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:api_key:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "api_key",
    pattern: /\b(AKIA[0-9A-Z]{16})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:api_key:${hash8}]`, redacted: true, secret: match };
    },
  },

  // 3. Webhook Secrets & JWT Tokens
  {
    type: "token",
    pattern: /\b(whsec_[0-9a-zA-Z+/=]{32,})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:token:${hash8}]`, redacted: true, secret: match };
    },
  },
  {
    type: "token",
    pattern: /\b(ey[A-Za-z0-9_-]{10,}\.ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b/g,
    apply: (match) => {
      if (match.startsWith("[REDACTED:")) return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(match);
      return { replaced: `[REDACTED:token:${hash8}]`, redacted: true, secret: match };
    },
  },

  // 4. Bearer Tokens
  {
    type: "bearer_token",
    pattern: /Bearer\s+([A-Za-z0-9\-_.~+/]+=*)/gi,
    apply: (match, token: string) => {
      if (!token || token.startsWith("[REDACTED:"))
        return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(token);
      return { replaced: `Bearer [REDACTED:bearer_token:${hash8}]`, redacted: true, secret: token };
    },
  },

  // 5. Connection Strings with embedded credentials
  {
    type: "connection_string",
    pattern:
      /((?:postgres|postgresql|mysql|mongodb|mongodb\+srv|redis|rediss):\/\/[^:]+:)([^@\s'"]+)(@[^\s'"]+)/gi,
    apply: (match, prefix: string, password: string, suffix: string) => {
      if (!password || password.startsWith("[REDACTED:"))
        return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(password);
      return {
        replaced: `${prefix}[REDACTED:connection_string:${hash8}]${suffix}`,
        redacted: true,
        secret: password,
      };
    },
  },

  // 6. Generic high-entropy secret assignments
  {
    type: "secret",
    pattern:
      /\b((?:password|passwd|secret|api_secret|auth_token|client_secret)\s*[:=]\s*["'])([^"'\r\n]{8,})(["'])/gi,
    apply: (match, prefix: string, secretVal: string, suffix: string) => {
      if (!secretVal || secretVal.startsWith("[REDACTED:"))
        return { replaced: match, redacted: false, secret: "" };
      const hash8 = computeRedactedTokenHash(secretVal);
      return {
        replaced: `${prefix}[REDACTED:secret:${hash8}]${suffix}`,
        redacted: true,
        secret: secretVal,
      };
    },
  },
];

/**
 * Scans text, replaces sensitive credentials with [REDACTED:<type>:<hash8>],
 * and returns the redacted text alongside audit counts.
 */
export function redactText(text: string): RedactionResult {
  if (!text) {
    return {
      redactedText: "",
      redactionCount: 0,
      countsByType: {},
    };
  }

  let result = text;
  let totalCount = 0;
  const countsByType: Record<string, number> = {};

  try {
    for (const rule of REDACTION_RULES) {
      const rx = new RegExp(rule.pattern.source, rule.pattern.flags);
      result = result.replace(rx, (match: string, ...args: unknown[]) => {
        const stringArgs = args.filter((a): a is string => typeof a === "string");
        const { replaced, redacted } = rule.apply(match, ...stringArgs);
        if (redacted) {
          totalCount++;
          countsByType[rule.type] = (countsByType[rule.type] || 0) + 1;
        }
        return replaced;
      });
    }

    return {
      redactedText: result,
      redactionCount: totalCount,
      countsByType,
    };
  } catch (err) {
    // Fail-closed (docs/07 §6): If redaction errors, never return potentially unredacted text
    throw new Error(`Secret redaction failed closed: ${String(err)}`, { cause: err });
  }
}
