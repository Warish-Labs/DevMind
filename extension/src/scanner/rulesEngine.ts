/**
 * DevMind Unified Local Rule Engine (docs/06 §8-§9).
 * Evaluates semantic facts, secret patterns, and credential path invariants.
 * Enforces:
 * 1. Evidence levels <= E1 (E0 or E1 only; no E2 or E3 locally).
 * 2. Deterministic secret redaction [REDACTED:token:hash8].
 * 3. Never labels findings as "vulnerable" (per AGENTS.md §5.7).
 */

import { Finding, ProjectModule } from "../types";
import { DiscoveredFile } from "./types";
import { evaluateAuthRules } from "./rules/authRules";
import { scanForSecrets } from "./rules/secretScanner";
import { evaluateCredentialFile } from "./rules/credentialFileRule";

export class LocalRuleEngine {
  /**
   * Evaluates all applicable local rules for a discovered file and its extracted modules.
   */
  public evaluate(
    file: DiscoveredFile,
    fileContent?: string,
    extractedModules: ProjectModule[] = []
  ): Finding[] {
    const findings: Finding[] = [];

    // 1. Path-only credential file rule (does not read file content)
    if (file.isCredential) {
      const credFinding = evaluateCredentialFile(file);
      if (credFinding) {
        findings.push(credFinding);
      }
      return findings;
    }

    // If no content (e.g. skipped binary or large file), cannot evaluate content rules
    if (!fileContent) {
      return findings;
    }

    // 2. Secret scan with deterministic redaction
    const secretFindings = scanForSecrets(fileContent, file.relativePath);
    findings.push(...secretFindings);

    // 3. Authorization & Authentication rules for extracted route modules
    for (const mod of extractedModules) {
      const authFindings = evaluateAuthRules(mod, fileContent);
      findings.push(...authFindings);
    }

    // Sanity filter: strictly enforce extension-local evidence level <= E1
    for (const f of findings) {
      if (f.evidenceLevel !== "E0" && f.evidenceLevel !== "E1") {
        f.evidenceLevel = "E1";
        f.evidenceLabel = "E1 · Possible";
      }
    }

    return findings;
  }
}
