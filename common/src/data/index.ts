import {
  RuleCatalog,
  RuleCatalogSchema,
  ReleaseStatus,
  ReleaseStatusSchema,
  PrivacyLedger,
  PrivacyLedgerSchema,
} from "../schemas/index.js";

export function validateRuleCatalog(data: unknown): RuleCatalog {
  return RuleCatalogSchema.parse(data);
}

export function validateReleaseStatus(data: unknown): ReleaseStatus {
  return ReleaseStatusSchema.parse(data);
}

export function validatePrivacyLedger(data: unknown): PrivacyLedger {
  return PrivacyLedgerSchema.parse(data);
}
