export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type EvidenceLevel = "E0" | "E1" | "E2" | "E3";
export type SyncMode = "metadata_only" | "indexed" | "disabled";

export interface Finding {
  id: string;
  ruleId: string;
  name: string;
  severity: Severity;
  category: string;
  evidenceLevel: EvidenceLevel;
  evidenceLabel: string;
  file: string;
  lineStart: number;
  lineEnd: number;
  message: string;
  codeSnippet?: string;
  remediation?: string;
}

export interface RouteDetail {
  method: string;
  path: string;
  auth: boolean;
  roleGuard: boolean;
  findingId?: string;
}

export interface ProjectModule {
  name: string;
  file: string;
  routes: RouteDetail[];
}

export interface DatabaseField {
  name: string;
  type: string;
  isPrimary?: boolean;
  isUnique?: boolean;
  isForeignKey?: boolean;
}

export interface DatabaseModel {
  name: string;
  sourceFile: string;
  fields: DatabaseField[];
}

export interface ExtensionSettings {
  apiBaseUrl: string;
  fixtureMode: boolean;
  syncMode: SyncMode;
}

export interface FindingsSource {
  getFindings(workspaceRoot?: string): Promise<Finding[]>;
  getStructure(workspaceRoot?: string): Promise<ProjectModule[]>;
  getDatabaseModels(workspaceRoot?: string): Promise<DatabaseModel[]>;
}
