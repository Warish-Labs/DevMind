import { z } from "zod";

export const SeverityLevelSchema = z.enum(["critical", "high", "medium", "low", "info"]);
export type SeverityLevel = z.infer<typeof SeverityLevelSchema>;

export const EvidenceLevelSchema = z.enum(["E0", "E1", "E2", "E3"]);
export type EvidenceLevel = z.infer<typeof EvidenceLevelSchema>;

export const RuleDefinitionSchema = z.object({
  rule_id: z.string().min(1),
  name: z.string().min(1),
  description: z.string(),
  severity: SeverityLevelSchema,
  category: z.string(),
  default_evidence_level: EvidenceLevelSchema,
});
export type RuleDefinition = z.infer<typeof RuleDefinitionSchema>;

export const RuleCatalogSchema = z.object({
  version: z.string(),
  rules: z.array(RuleDefinitionSchema),
});
export type RuleCatalog = z.infer<typeof RuleCatalogSchema>;

export const ReleaseStatusSchema = z.object({
  projectStatus: z.enum(["specification", "building", "mvp", "stable"]),
  lastUpdated: z.string(),
  capabilities: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      release: z.enum(["mvp", "1.1", "1.2", "1.3", "1.4"]),
      status: z.enum(["planned", "in-progress", "available"]),
    })
  ),
});
export type ReleaseStatus = z.infer<typeof ReleaseStatusSchema>;

export const PrivacyLedgerEntrySchema = z.object({
  category: z.string(),
  staysLocal: z.boolean(),
  storedInDevMind: z.boolean(),
  embedded: z.boolean(),
  reachesLLM: z.boolean(),
  modes: z.array(z.enum(["metadata_only", "indexed"])),
});
export type PrivacyLedgerEntry = z.infer<typeof PrivacyLedgerEntrySchema>;

export const PrivacyLedgerSchema = z.object({
  version: z.string(),
  entries: z.array(PrivacyLedgerEntrySchema),
});
export type PrivacyLedger = z.infer<typeof PrivacyLedgerSchema>;

export const CapabilitySchema = z.object({
  id: z.string(),
  question: z.string(),
  capability: z.string(),
  release: z.string(),
  summary: z.string(),
});
export type Capability = z.infer<typeof CapabilitySchema>;

export const CapabilitiesCatalogSchema = z.array(CapabilitySchema);
export type CapabilitiesCatalog = z.infer<typeof CapabilitiesCatalogSchema>;

export const WalkthroughStepSchema = z.object({
  step: z.number().int().positive(),
  title: z.string(),
  agent: z.string(),
  brainState: z.string(),
  status: z.enum(["mvp", "planned"]),
});
export type WalkthroughStep = z.infer<typeof WalkthroughStepSchema>;

export const WalkthroughCatalogSchema = z.array(WalkthroughStepSchema);
export type WalkthroughCatalog = z.infer<typeof WalkthroughCatalogSchema>;
