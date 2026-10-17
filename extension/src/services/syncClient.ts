/**
 * DevMind Extension Cloud Sync Client (Milestone M4-09, docs/06 §9, §11, docs/03 §11.2).
 *
 * Coordinates metadata-only synchronization from local workspace to DevMind cloud:
 * 1. Computes manifest diff against cloud Project Brain (POST /api/v1/ext/projects/{pid}/manifest/diff).
 * 2. Recovers automatically from base snapshot drift (409 sync.stale_base).
 * 3. Registers new/changed files and records removed files (PUT /api/v1/ext/projects/{pid}/manifest).
 * 4. Batches extracted code symbols (PUT /api/v1/ext/projects/{pid}/symbols).
 * 5. Batches extracted code relationships (PUT /api/v1/ext/projects/{pid}/relationships).
 * 6. Ingests scanner findings capped at evidence level <= E1 (POST /api/v1/ext/projects/{pid}/findings:batch).
 * 7. Updates local manifest sync receipts and saves outside repository.
 *
 * Adheres strictly to:
 * - Rule 5 & ADR-047: Zero unconsented source text uploaded at rest.
 * - Rule 10: Extension endpoints authenticate via ExtensionAuthService (Bearer dme_at_...).
 * - Evidence ceiling: Scanner findings strictly capped at E1.
 */

import { DatabaseModel, Finding, ProjectModule } from "../types";
import { LocalManifestStore } from "../scanner/manifest";
import { computeNormalizedTextHash } from "../scanner/hasher";
import { ExtensionAuthService } from "./auth";
import { DevMindLogger } from "./logger";
import { SettingsService } from "./settings";

export interface SyncOptions {
  projectId: string;
  workspaceRoot: string;
  manifestStore: LocalManifestStore;
  findings: Finding[];
  modules: ProjectModule[];
  databaseModels: DatabaseModel[];
  baseSnapshotId?: string;
  scanRunId?: string;
  onProgress?: (message: string, pct: number) => void;
}

export interface SyncResult {
  success: boolean;
  projectId: string;
  filesCount: number;
  versionsCreated: number;
  removedCount: number;
  symbolsCount: number;
  relationshipsCount: number;
  findingsIngested: number;
  staleBaseRecovered: boolean;
  error?: string;
}

export class SyncClient {
  private logger = DevMindLogger.get();
  private authService: ExtensionAuthService;

  constructor(authService?: ExtensionAuthService) {
    this.authService = authService ?? ExtensionAuthService.get();
  }

  /**
   * Executes complete metadata-only cloud sync pass.
   */
  public async sync(options: SyncOptions): Promise<SyncResult> {
    const { projectId, manifestStore, findings, modules, databaseModels, scanRunId, onProgress } =
      options;

    const settings = SettingsService.get();
    const apiBase = settings.apiBaseUrl.replace(/\/+$/, "");

    this.logger.info("Starting Project Brain metadata sync", { projectId });
    onProgress?.("Resolving extension credentials...", 10);

    // 1. Resolve authentication token
    let token = await this.authService.getAccessToken();
    if (!token) {
      this.logger.warn("Sync aborted: user not authenticated or tokens expired");
      return {
        success: false,
        projectId,
        filesCount: 0,
        versionsCreated: 0,
        removedCount: 0,
        symbolsCount: 0,
        relationshipsCount: 0,
        findingsIngested: 0,
        staleBaseRecovered: false,
        error: "Not authenticated. Please sign in via DevMind: Sign In.",
      };
    }

    const headers = (tok: string) => ({
      "Content-Type": "application/json",
      Authorization: `Bearer ${tok}`,
      "X-DevMind-Client": "extension/0.1.1",
    });

    let staleBaseRecovered = false;
    let baseSnapshotId = options.baseSnapshotId;

    // Helper for authenticated requests with single 401 retry
    const authFetch = async (url: string, init: RequestInit): Promise<Response> => {
      let res = await fetch(url, { ...init, headers: headers(token!) });
      if (res.status === 401) {
        this.logger.info("Sync received 401 Unauthorized; attempting token refresh");
        const refreshToken = await this.authService.getRefreshToken();
        if (refreshToken) {
          const refreshed = await this.authService.refreshTokens(refreshToken);
          if (refreshed) {
            token = refreshed.accessToken;
            res = await fetch(url, { ...init, headers: headers(token) });
          }
        }
      }
      return res;
    };

    try {
      // 2. Prepare manifest records
      const allRecords = manifestStore.getAllRecords();
      const filesPayload = allRecords.map((r) => ({
        path: r.relativePath,
        content_hash: r.contentHash,
        size_bytes: r.size,
        line_count: 0,
        language: r.languageId,
        tier: r.languageTier,
      }));

      onProgress?.("Calculating manifest diff against Project Brain...", 25);

      // 3. POST /ext/projects/{pid}/manifest/diff
      const diffUrl = `${apiBase}/ext/projects/${projectId}/manifest/diff`;
      let diffRes = await authFetch(diffUrl, {
        method: "POST",
        body: JSON.stringify({
          scan_run_id: scanRunId,
          base_snapshot_id: baseSnapshotId,
          files: filesPayload,
        }),
      });

      // Handle 409 sync.stale_base (docs/06 §13)
      if (diffRes.status === 409) {
        this.logger.info(
          "Base snapshot is stale (409 sync.stale_base); re-diffing from clean base"
        );
        staleBaseRecovered = true;
        baseSnapshotId = undefined;

        diffRes = await authFetch(diffUrl, {
          method: "POST",
          body: JSON.stringify({
            scan_run_id: scanRunId,
            base_snapshot_id: undefined,
            files: filesPayload,
          }),
        });
      }

      if (!diffRes.ok) {
        const errDetail = await diffRes.text();
        throw new Error(`Manifest diff failed (${diffRes.status}): ${errDetail}`);
      }

      const diffData = (await diffRes.json()) as {
        unchanged: number;
        new: number;
        changed: number;
        removed: string[];
        missing_files: Array<{ path: string; reason: string }>;
      };

      this.logger.info("Manifest diff computed", {
        unchanged: diffData.unchanged,
        new: diffData.new,
        changed: diffData.changed,
        removed: diffData.removed.length,
      });

      onProgress?.("Uploading file versions and manifest...", 45);

      // 4. PUT /ext/projects/{pid}/manifest
      // Upload all new, changed, or pending files
      const manifestUrl = `${apiBase}/ext/projects/${projectId}/manifest`;
      const putRes = await authFetch(manifestUrl, {
        method: "PUT",
        body: JSON.stringify({
          scan_run_id: scanRunId,
          base_snapshot_id: baseSnapshotId,
          files: filesPayload,
          removed_paths: diffData.removed,
        }),
      });

      if (!putRes.ok) {
        const errDetail = await putRes.text();
        throw new Error(`Manifest upload failed (${putRes.status}): ${errDetail}`);
      }

      const putData = (await putRes.json()) as {
        files_count: number;
        versions_created: number;
        removed_count: number;
      };

      onProgress?.("Extracting and uploading code symbols...", 65);

      // 5. Build and upload symbols
      const symbolsPayload: Array<{
        path: string;
        name: string;
        qualified_name: string;
        kind: string;
        signature?: string;
        start_line: number;
        end_line: number;
        framework_tags: Record<string, unknown>;
      }> = [];

      // Extract route symbols from modules
      for (const mod of modules) {
        for (const route of mod.routes) {
          symbolsPayload.push({
            path: mod.file,
            name: route.path,
            qualified_name: `${route.method}:${route.path}`,
            kind: "route",
            signature: `${route.method} ${route.path}`,
            start_line: route.lineStart ?? 1,
            end_line: route.lineEnd ?? 1,
            framework_tags: {
              auth: route.auth,
              roleGuard: route.roleGuard,
              findingId: route.findingId,
            },
          });
        }
      }

      // Extract model symbols from database models
      for (const model of databaseModels) {
        symbolsPayload.push({
          path: model.sourceFile,
          name: model.name,
          qualified_name: `model.${model.name}`,
          kind: "model",
          signature: `model ${model.name}`,
          start_line: 1,
          end_line: 1,
          framework_tags: {
            fieldNames: model.fields.map((f) => f.name),
          },
        });
      }

      let symbolsCount = 0;
      if (symbolsPayload.length > 0) {
        const symbolsUrl = `${apiBase}/ext/projects/${projectId}/symbols`;
        const symRes = await authFetch(symbolsUrl, {
          method: "PUT",
          body: JSON.stringify({
            scan_run_id: scanRunId,
            symbols: symbolsPayload,
          }),
        });

        if (!symRes.ok) {
          const errDetail = await symRes.text();
          throw new Error(`Symbols upload failed (${symRes.status}): ${errDetail}`);
        }

        const symData = (await symRes.json()) as { upserted: number };
        symbolsCount = symData.upserted;
      }

      onProgress?.("Uploading relationships and graph edges...", 80);

      // 6. Build and upload structural relationships
      const relationshipsPayload: Array<{
        source_path: string;
        source_symbol_key: string;
        target_path?: string;
        target_symbol_key: string;
        kind: string;
        confidence: number;
        metadata: Record<string, unknown>;
      }> = [];

      for (const mod of modules) {
        for (const route of mod.routes) {
          // If route is guarded, emit relationship
          if (route.roleGuard) {
            relationshipsPayload.push({
              source_path: mod.file,
              source_symbol_key: `${route.method}:${route.path}`,
              target_symbol_key: "auth.roleGuard",
              kind: "guarded_by",
              confidence: 1.0,
              metadata: { roleGuard: true },
            });
          }
        }
      }

      let relationshipsCount = 0;
      if (relationshipsPayload.length > 0) {
        const relUrl = `${apiBase}/ext/projects/${projectId}/relationships`;
        const relRes = await authFetch(relUrl, {
          method: "PUT",
          body: JSON.stringify({
            scan_run_id: scanRunId,
            relationships: relationshipsPayload,
          }),
        });

        if (!relRes.ok) {
          const errDetail = await relRes.text();
          throw new Error(`Relationships upload failed (${relRes.status}): ${errDetail}`);
        }

        const relData = (await relRes.json()) as { upserted: number };
        relationshipsCount = relData.upserted;
      }

      onProgress?.("Uploading security findings (evidence <= E1)...", 90);

      // 7. Upload findings batch with evidence strictly <= E1 (Rule 5 invariant)
      const findingsPayload = findings.map((f) => {
        const snippetText = f.codeSnippet || f.file;
        const snippetHash = "sha256:" + computeNormalizedTextHash(snippetText);

        return {
          rule_id: f.ruleId,
          category: f.category || "security",
          title: f.name,
          summary: f.message,
          explanation: f.remediation,
          severity: f.severity,
          confidence: "high",
          evidence_level: "E1", // Enforce evidence ceiling
          location: {
            path: f.file,
            start_line: f.lineStart,
            end_line: f.lineEnd,
          },
          evidence: [
            {
              role: "primary",
              path: f.file,
              start_line: f.lineStart,
              end_line: f.lineEnd,
              snippet_hash: snippetHash,
              detail: {
                ruleId: f.ruleId,
                evidenceLabel: f.evidenceLabel,
              },
            },
          ],
        };
      });

      let findingsIngested = 0;
      if (findingsPayload.length > 0) {
        const findingsUrl = `${apiBase}/ext/projects/${projectId}/findings:batch`;
        const findRes = await authFetch(findingsUrl, {
          method: "POST",
          body: JSON.stringify({
            scan_run_id: scanRunId,
            findings: findingsPayload,
          }),
        });

        if (!findRes.ok) {
          const errDetail = await findRes.text();
          throw new Error(`Findings batch upload failed (${findRes.status}): ${errDetail}`);
        }

        const findData = (await findRes.json()) as { ingested: number };
        findingsIngested = findData.ingested;
      }

      // 8. Update manifest sync receipts and save store
      for (const rec of allRecords) {
        manifestStore.markSynced(rec.relativePath, rec.contentHash);
      }
      await manifestStore.save();

      onProgress?.("Metadata sync complete!", 100);
      this.logger.info("Sync complete", {
        filesCount: putData.files_count,
        versionsCreated: putData.versions_created,
        symbolsCount,
        relationshipsCount,
        findingsIngested,
      });

      return {
        success: true,
        projectId,
        filesCount: putData.files_count,
        versionsCreated: putData.versions_created,
        removedCount: putData.removed_count,
        symbolsCount,
        relationshipsCount,
        findingsIngested,
        staleBaseRecovered,
      };
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.logger.error("Project Brain sync failed", { error: errMsg });
      return {
        success: false,
        projectId,
        filesCount: 0,
        versionsCreated: 0,
        removedCount: 0,
        symbolsCount: 0,
        relationshipsCount: 0,
        findingsIngested: 0,
        staleBaseRecovered,
        error: errMsg,
      };
    }
  }
}
