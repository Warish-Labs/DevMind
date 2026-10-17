/**
 * DevMind Credential File Rule (docs/06 §4).
 * Evaluates path-only exposure of sensitive credential files without reading file content.
 */

import { Finding } from "../../types";
import { DiscoveredFile } from "../types";

export function evaluateCredentialFile(file: DiscoveredFile): Finding | null {
  if (!file.isCredential) {
    return null;
  }

  return {
    id: `env-${file.relativePath.replace(/[^a-zA-Z0-9]/g, "-")}`,
    ruleId: "devmind.secrets.exposed_env_file",
    name: "Credential File Present in Workspace",
    severity: "medium",
    category: "secrets",
    evidenceLevel: "E1",
    evidenceLabel: "E1 · Possible",
    file: file.relativePath,
    lineStart: 1,
    lineEnd: 1,
    message: `Potential credential exposure: Configuration file '${file.relativePath}' detected in workspace.`,
    remediation:
      "Ensure credential files are listed in .gitignore and .devmindignore to prevent accidental commit.",
  };
}
