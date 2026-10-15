# Security Policy

DevMind is committed to ensuring the security and privacy of its users, software, and data.

## Reporting a Vulnerability

If you discover a security vulnerability in DevMind, please **do not** open a public issue.

Please report vulnerabilities privately:

1. **GitHub Security Advisories (Recommended):**
   Go to the [DevMind Security Advisories tab](https://github.com/Warish-Labs/DevMind/security/advisories) and click **Report a vulnerability**.
2. **Email:**
   Send an encrypted or private email to **security@warishlabs.in** (or **warishdeveloper@gmail.com**) with the subject `[SECURITY] Potential Vulnerability in DevMind`.

Please include:
- A description of the issue and potential impact
- Affected component(s) (`client`, `server`, `extension`, `common`)
- Step-by-step reproduction instructions or a minimal proof of concept
- Any potential mitigations you have identified

## Response Timeline

- **Initial Acknowledgement:** Within 48 hours.
- **Triage and Assessment:** Within 5 business days.
- **Resolution and Disclosure:** Coordinated with the reporter prior to public release.

## Scope and Principles

- **Never execute repository code:** DevMind static analysis and scanners never execute untrusted project code.
- **Redaction by default:** All tokens, credentials, and secrets are redacted before transmission or logging.
- **Consent first:** No repository source code or context leaves the user's machine without explicit, recorded consent.
