import {
  RuleCatalog,
  RuleCatalogSchema,
  ReleaseStatus,
  ReleaseStatusSchema,
  PrivacyLedger,
  PrivacyLedgerSchema,
  CapabilitiesCatalog,
  CapabilitiesCatalogSchema,
  WalkthroughCatalog,
  WalkthroughCatalogSchema,
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

export function validateCapabilities(data: unknown): CapabilitiesCatalog {
  return CapabilitiesCatalogSchema.parse(data);
}

export function validateWalkthrough(data: unknown): WalkthroughCatalog {
  return WalkthroughCatalogSchema.parse(data);
}
