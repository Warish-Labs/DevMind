import { describe, it, expect } from "vitest";
import path from "node:path";
import fs from "node:fs/promises";
import { SemanticExtractor } from "../src/scanner/extractor";
import {
  extractExpressRoutes,
  extractNextJsRoutes,
  extractPrismaModels,
} from "../src/scanner/extractors/typescriptExtractor";
import {
  extractFastApiRoutes,
  extractSqlAlchemyModels,
} from "../src/scanner/extractors/pythonExtractor";

const ROOT = path.resolve(__dirname, "../../");
const EXPRESS_ADMIN_FILE = path.join(
  ROOT,
  "evals/scanner/fixtures/express-admin/src/routes/admin.ts"
);
const FASTAPI_ADMIN_FILE = path.join(
  ROOT,
  "evals/scanner/fixtures/fastapi-admin/app/routes/admin.py"
);

describe("Semantic Parsers and Extractors (docs/06 §8)", () => {
  const extractor = new SemanticExtractor();

  describe("Express Routes Extraction", () => {
    it("extracts Express routes with auth and role guards from real fixture", async () => {
      const content = await fs.readFile(EXPRESS_ADMIN_FILE, "utf-8");
      const mod = extractExpressRoutes(content, "src/routes/admin.ts");

      expect(mod).toBeDefined();
      expect(mod?.name).toBe("admin");
      expect(mod?.file).toBe("src/routes/admin.ts");
      expect(mod?.routes).toHaveLength(2);

      // Route 1: /admin/users (Vulnerable: auth=true, roleGuard=false)
      const r1 = mod?.routes[0];
      expect(r1?.method).toBe("GET");
      expect(r1?.path).toBe("/admin/users");
      expect(r1?.auth).toBe(true);
      expect(r1?.roleGuard).toBe(false);
      expect(r1?.lineStart).toBe(7);

      // Route 2: /admin/users/:id (Safe: auth=true, roleGuard=true)
      const r2 = mod?.routes[1];
      expect(r2?.method).toBe("DELETE");
      expect(r2?.path).toBe("/admin/users/:id");
      expect(r2?.auth).toBe(true);
      expect(r2?.roleGuard).toBe(true);
      expect(r2?.lineStart).toBe(12);
    });
  });

  describe("FastAPI Routes Extraction", () => {
    it("extracts FastAPI router endpoints with combined prefix and guards from real fixture", async () => {
      const content = await fs.readFile(FASTAPI_ADMIN_FILE, "utf-8");
      const mod = extractFastApiRoutes(content, "app/routes/admin.py");

      expect(mod).toBeDefined();
      expect(mod?.name).toBe("admin");
      expect(mod?.routes).toHaveLength(2);

      // Endpoint 1: /admin/users (auth=true, roleGuard=false)
      const ep1 = mod?.routes[0];
      expect(ep1?.method).toBe("GET");
      expect(ep1?.path).toBe("/admin/users");
      expect(ep1?.auth).toBe(true);
      expect(ep1?.roleGuard).toBe(false);
      expect(ep1?.lineStart).toBe(7);

      // Endpoint 2: /admin/users/{user_id} (auth=true, roleGuard=true)
      const ep2 = mod?.routes[1];
      expect(ep2?.method).toBe("DELETE");
      expect(ep2?.path).toBe("/admin/users/{user_id}");
      expect(ep2?.auth).toBe(true);
      expect(ep2?.roleGuard).toBe(true);
      expect(ep2?.lineStart).toBe(12);
    });
  });

  describe("Next.js App Router Extraction", () => {
    it("extracts HTTP methods from Next.js route handler", () => {
      const code = `
        import { NextResponse } from "next/server";
        import { auth } from "@/auth";

        export async function GET(request: Request) {
          const session = await auth();
          return NextResponse.json({ ok: true });
        }

        export async function POST(request: Request) {
          return NextResponse.json({ created: true });
        }
      `;

      const mod = extractNextJsRoutes(code, "app/api/workspaces/[id]/route.ts");
      expect(mod).toBeDefined();
      expect(mod?.routes).toHaveLength(2);

      const getRoute = mod?.routes.find((r) => r.method === "GET");
      expect(getRoute?.path).toBe("/api/workspaces/:id");
      expect(getRoute?.auth).toBe(true);
    });
  });

  describe("Prisma Model Extraction", () => {
    it("extracts model fields, primary keys, and relationships", () => {
      const prismaContent = `
        model User {
          id        String   @id @default(uuid())
          email     String   @unique
          posts     Post[]
          createdAt DateTime @default(now())
        }

        model Post {
          id       Int    @id @default(autoincrement())
          title    String
          authorId String
          author   User   @relation(fields: [authorId], references: [id])
        }
      `;

      const models = extractPrismaModels(prismaContent, "prisma/schema.prisma");
      expect(models).toHaveLength(2);

      const userModel = models.find((m) => m.name === "User");
      expect(userModel?.fields.find((f) => f.name === "id")?.isPrimary).toBe(true);
      expect(userModel?.fields.find((f) => f.name === "email")?.isUnique).toBe(true);

      const postModel = models.find((m) => m.name === "Post");
      expect(postModel?.fields.find((f) => f.name === "author")?.isForeignKey).toBe(true);
    });
  });

  describe("SQLAlchemy Model Extraction", () => {
    it("extracts declarative SQLAlchemy models and columns", () => {
      const pythonModelCode = `
        from sqlalchemy import Column, String, UUID, ForeignKey
        from app.db.base import Base

        class Project(Base):
            __tablename__ = "projects"
            id = Column(UUID, primary_key=True)
            name = Column(String, unique=True)
            workspace_id = Column(UUID, ForeignKey("workspaces.id"))
      `;

      const models = extractSqlAlchemyModels(pythonModelCode, "app/models/project.py");
      expect(models).toHaveLength(1);

      const proj = models[0];
      expect(proj.name).toBe("Project");
      expect(proj.fields).toHaveLength(3);
      expect(proj.fields.find((f) => f.name === "id")?.isPrimary).toBe(true);
      expect(proj.fields.find((f) => f.name === "name")?.isUnique).toBe(true);
      expect(proj.fields.find((f) => f.name === "workspace_id")?.isForeignKey).toBe(true);
    });
  });

  describe("Unified SemanticExtractor Dispatcher", () => {
    it("dispatches and collects symbols and relationship metrics", async () => {
      const content = await fs.readFile(EXPRESS_ADMIN_FILE, "utf-8");
      const result = extractor.extract(content, "src/routes/admin.ts");

      expect(result.modules).toHaveLength(1);
      expect(result.symbolCount).toBe(2);
      expect(result.relationshipCount).toBe(2);
    });
  });
});
