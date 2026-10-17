import { describe, expect, it } from "vitest";
import { redactText } from "../src/scanner/redaction";
import { computeRedactedTokenHash } from "../src/scanner/hasher";

describe("extension/scanner/redaction", () => {
  it("redacts API keys and cloud credentials deterministically", () => {
    const rawStripe = ["sk", "live", "1234567890abcdef12345678"].join("_");
    const rawAnthropic = ["sk", "ant", "api03-abcdefghijklmnopqrstuvwxyz1234567890"].join("-");
    const rawOpenAI = ["sk", "abcdefghijklmnopqrstuvwxyz1234567890"].join("-");
    const rawGitHub = ["ghp", "1234567890abcdefghijklmnopqrstuvwxyz"].join("_");
    const rawAws = "AKIA1234567890ABCDEF";

    const input = [
      `STRIPE_KEY = "${rawStripe}"`,
      `ANTHROPIC_KEY = "${rawAnthropic}"`,
      `OPENAI_KEY = "${rawOpenAI}"`,
      `GITHUB_TOKEN = "${rawGitHub}"`,
      `AWS_ACCESS_KEY = "${rawAws}"`,
    ].join("\n");

    const result = redactText(input);

    expect(result.redactionCount).toBe(5);
    expect(result.countsByType.api_key).toBe(5);

    // Assert raw values are completely gone
    expect(result.redactedText).not.toContain(rawStripe);
    expect(result.redactedText).not.toContain(rawAnthropic);
    expect(result.redactedText).not.toContain(rawOpenAI);
    expect(result.redactedText).not.toContain(rawGitHub);
    expect(result.redactedText).not.toContain(rawAws);

    // Assert format [REDACTED:api_key:<hash8>]
    expect(result.redactedText).toContain(
      `[REDACTED:api_key:${computeRedactedTokenHash(rawStripe)}]`
    );
    expect(result.redactedText).toContain(
      `[REDACTED:api_key:${computeRedactedTokenHash(rawAnthropic)}]`
    );
    expect(result.redactedText).toContain(
      `[REDACTED:api_key:${computeRedactedTokenHash(rawOpenAI)}]`
    );
    expect(result.redactedText).toContain(
      `[REDACTED:api_key:${computeRedactedTokenHash(rawGitHub)}]`
    );
    expect(result.redactedText).toContain(`[REDACTED:api_key:${computeRedactedTokenHash(rawAws)}]`);
  });

  it("redacts private keys (full block and single line)", () => {
    const privateKey = [
      "-----BEGIN RSA PRIVATE KEY-----",
      "MIIEowIBAAKCAQEA0Y1...",
      "-----END RSA PRIVATE KEY-----",
    ].join("\n");

    const input = `const key = \`${privateKey}\`;`;
    const result = redactText(input);

    expect(result.redactionCount).toBe(1);
    expect(result.countsByType.private_key).toBe(1);
    expect(result.redactedText).not.toContain("MIIEowIBAAKCAQEA0Y1...");
    expect(result.redactedText).toContain(
      `[REDACTED:private_key:${computeRedactedTokenHash(privateKey)}]`
    );
  });

  it("redacts bearer tokens and connection strings while preserving structural context", () => {
    const rawToken = "dme_at_super_secret_bearer_token_12345";
    const rawPass = "superSecretPassword123!";
    const input = [
      `Authorization: Bearer ${rawToken}`,
      `DATABASE_URL=postgres://devmind_user:${rawPass}@localhost:5432/devmind_db`,
    ].join("\n");

    const result = redactText(input);

    expect(result.redactionCount).toBe(2);
    expect(result.countsByType.bearer_token).toBe(1);
    expect(result.countsByType.connection_string).toBe(1);

    expect(result.redactedText).not.toContain(rawToken);
    expect(result.redactedText).not.toContain(rawPass);

    expect(result.redactedText).toContain(
      `Authorization: Bearer [REDACTED:bearer_token:${computeRedactedTokenHash(rawToken)}]`
    );
    expect(result.redactedText).toContain(
      `DATABASE_URL=postgres://devmind_user:[REDACTED:connection_string:${computeRedactedTokenHash(rawPass)}]@localhost:5432/devmind_db`
    );
  });

  it("redacts webhook secrets and generic password assignments", () => {
    const rawWhsec = ["whsec", "5432109876543210abcdefghijklmnop"].join("_");
    const rawJwt =
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGz64flt_example_signature_12345";
    const rawPassword = "mySuperP@ssw0rd!!";

    const input = [
      `WEBHOOK_SECRET = "${rawWhsec}"`,
      `JWT_TOKEN = "${rawJwt}"`,
      `const client_secret = "${rawPassword}";`,
    ].join("\n");

    const result = redactText(input);

    expect(result.redactionCount).toBe(3);
    expect(result.countsByType.token).toBe(2);
    expect(result.countsByType.secret).toBe(1);

    expect(result.redactedText).not.toContain(rawWhsec);
    expect(result.redactedText).not.toContain(rawJwt);
    expect(result.redactedText).not.toContain(rawPassword);

    expect(result.redactedText).toContain(`[REDACTED:token:${computeRedactedTokenHash(rawWhsec)}]`);
    expect(result.redactedText).toContain(`[REDACTED:token:${computeRedactedTokenHash(rawJwt)}]`);
    expect(result.redactedText).toContain(
      `client_secret = "[REDACTED:secret:${computeRedactedTokenHash(rawPassword)}]"`
    );
  });

  it("produces identical hashes for repeat tokens (correlation) and does not double-redact", () => {
    const token = ["sk", "live", "repeattoken1234567890abcdef"].join("_");
    const input = `Key1: ${token}\nKey2: ${token}`;

    const firstPass = redactText(input);
    expect(firstPass.redactionCount).toBe(2);

    const hash8 = computeRedactedTokenHash(token);
    const expectedPlaceholder = `[REDACTED:api_key:${hash8}]`;
    expect(firstPass.redactedText).toBe(
      `Key1: ${expectedPlaceholder}\nKey2: ${expectedPlaceholder}`
    );

    // Second pass on already redacted text must be a no-op
    const secondPass = redactText(firstPass.redactedText);
    expect(secondPass.redactionCount).toBe(0);
    expect(secondPass.redactedText).toBe(firstPass.redactedText);
  });

  it("handles empty or safe text without modifications", () => {
    expect(redactText("").redactedText).toBe("");
    expect(redactText("").redactionCount).toBe(0);

    const safeCode = `
      function add(a: number, b: number): number {
        return a + b;
      }
    `;
    const result = redactText(safeCode);
    expect(result.redactionCount).toBe(0);
    expect(result.redactedText).toBe(safeCode);
  });
});
