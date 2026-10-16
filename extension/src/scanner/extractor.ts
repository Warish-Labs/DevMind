/**
 * DevMind Unified Semantic Extraction Dispatcher (docs/06 §8).
 * Extracts routes, symbols, guards, and models across supported frameworks.
 */

import { DatabaseModel, ProjectModule } from "../types";
import {
  extractExpressRoutes,
  extractNextJsRoutes,
  extractPrismaModels,
} from "./extractors/typescriptExtractor";
import { extractFastApiRoutes, extractSqlAlchemyModels } from "./extractors/pythonExtractor";

export interface SemanticExtractionResult {
  modules: ProjectModule[];
  models: DatabaseModel[];
  symbolCount: number;
  relationshipCount: number;
}

export class SemanticExtractor {
  /**
   * Extracts architectural modules (routes) and database models from file content.
   */
  public extract(content: string, relPath: string): SemanticExtractionResult {
    const modules: ProjectModule[] = [];
    const models: DatabaseModel[] = [];

    const ext = relPath.slice(relPath.lastIndexOf(".")).toLowerCase();

    // 1. TypeScript / JavaScript
    if (ext === ".ts" || ext === ".tsx" || ext === ".js" || ext === ".jsx") {
      const expressMod = extractExpressRoutes(content, relPath);
      if (expressMod) {
        modules.push(expressMod);
      }

      const nextMod = extractNextJsRoutes(content, relPath);
      if (nextMod) {
        modules.push(nextMod);
      }
    }

    // 2. Prisma
    if (ext === ".prisma") {
      const prismaModels = extractPrismaModels(content, relPath);
      models.push(...prismaModels);
    }

    // 3. Python
    if (ext === ".py") {
      const fastApiMod = extractFastApiRoutes(content, relPath);
      if (fastApiMod) {
        modules.push(fastApiMod);
      }

      const saModels = extractSqlAlchemyModels(content, relPath);
      models.push(...saModels);
    }

    // Compute basic symbol and relationship metrics
    let symbolCount = 0;
    let relationshipCount = 0;

    for (const mod of modules) {
      symbolCount += mod.routes.length;
      relationshipCount += mod.routes.filter((r) => r.auth || r.roleGuard).length;
    }

    for (const model of models) {
      symbolCount += 1 + model.fields.length;
      relationshipCount += model.fields.filter((f) => f.isForeignKey).length;
    }

    return {
      modules,
      models,
      symbolCount,
      relationshipCount,
    };
  }
}
