/**
 * DevMind Secret Scanner with Deterministic Redaction (docs/06 §8, docs/07 §6).
 * Scans content for secrets and applies deterministic redaction [REDACTED:token:hash8].
 * NEVER leaks raw secret tokens into findings or code snippets.
 */

import { Finding } from "../../types";
import { computeRedactedTokenHash } from "../hasher";

interface SecretPattern {
  name: string;
  regex: RegExp;
  category: string;
  ruleId: string;
}

const SECRET_PATTERNS: SecretPattern[] = [
  {
    name: "Stripe Live Secret Key",
    regex: /\b(sk_live_[0-9a-zA-Z]{24,})\b/g,
    category: "secrets",
    ruleId: "devmind.secrets.hardcoded_credential",
  },
  {
    name: "GitHub Personal Access Token",
    regex: /\b(ghp_[0-9a-zA-Z]{36})\b/g,
    category: "secrets",
    ruleId: "devmind.secrets.hardcoded_credential",
  },
  {
    name: "AWS Access Key ID",
    regex: /\b(AKIA[0-9A-Z]{16})\b/g,
    category: "secrets",
    ruleId: "devmind.secrets.hardcoded_credential",
  },
  {
    name: "Private Key Header",
    regex: /(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)/g,
    category: "secrets",
    ruleId: "devmind.secrets.hardcoded_credential",
  },
  {
    name: "Clerk Live Secret Key",
    regex: /\b(sk_live_[0-9a-zA-Z]{32,})\b/g,
    category: "secrets",
    ruleId: "devmind.secrets.hardcoded_credential",
  },
  {
    name: "Clerk Webhook Secret",
    regex: /\b(whsec_[0-9a-zA-Z+/=]{32,})\b/g,
    category: "secrets",
    ruleId: "devmind.secrets.hardcoded_credential",
  },
];

export function scanForSecrets(content: string, relPath: string): Finding[] {
  const findings: Finding[] = [];
  const lines = content.split(/\r?\n/);

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
    const line = lines[lineIndex];
    if (!line) {
      continue;
    }

    for (const pat of SECRET_PATTERNS) {
      // Reset regex state
      pat.regex.lastIndex = 0;
      let match: RegExpExecArray | null;

      while ((match = pat.regex.exec(line)) !== null) {
        const rawSecret = match[1] || match[0];
        const hash8 = computeRedactedTokenHash(rawSecret);
        const redactedToken = `[REDACTED:token:${hash8}]`;

        // Produce a safely redacted code snippet
        const lineNum = lineIndex + 1;
        const redactedSnippet = line.replace(rawSecret, redactedToken).trim();

        const findingId = `sec-${hash8}-${lineNum}`;

        findings.push({
          id: findingId,
          ruleId: pat.ruleId,
          name: "Hardcoded Credential Detected",
          severity: "critical",
          category: pat.category,
          evidenceLevel: "E1",
          evidenceLabel: "E1 · Possible",
          file: relPath,
          lineStart: lineNum,
          lineEnd: lineNum,
          message: `Hardcoded ${pat.name} detected. Secrets must never be stored in source code.`,
          codeSnippet: redactedSnippet,
          remediation: "Move credentials to environment variables or a secure key store.",
        });
      }
    }
  }

  return findings;
}
