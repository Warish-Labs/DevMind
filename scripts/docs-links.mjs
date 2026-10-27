#!/usr/bin/env node

/**
 * scripts/docs-links.mjs
 * Validates relative links, anchor fragments, Mermaid diagram syntax,
 * ADR/OQ references, and brand asset consistency across all Markdown files.
 *
 * Usage:
 *   node scripts/docs-links.mjs
 *   node scripts/docs-links.mjs --verbose
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const REPO_ROOT = process.cwd();
const VERBOSE = process.argv.includes("--verbose") || process.argv.includes("-v");

const IGNORED_DIRS = new Set([
  ".git",
  ".gemini",
  "node_modules",
  "dist",
  ".next",
  "reports",
  "coverage",
  ".venv",
  "out",
  ".turbo",
]);

const ALLOWED_MERMAID_TYPES = new Set([
  "flowchart",
  "graph",
  "sequenceDiagram",
  "stateDiagram-v2",
  "stateDiagram",
  "classDiagram",
  "erDiagram",
  "xychart-beta",
]);

/**
 * Recursively find all Markdown files.
 */
function findMarkdownFiles(dir) {
  let files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (!IGNORED_DIRS.has(entry.name)) {
        files.push(...findMarkdownFiles(path.join(dir, entry.name)));
      }
    } else if (entry.name.endsWith(".md")) {
      files.push(path.join(dir, entry.name));
    }
  }
  return files;
}

/**
 * Standard GitHub slug generator for Markdown headings.
 */
function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/<[^>]+>/g, "") // remove HTML tags if present in heading
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-");
}

/**
 * Extract all anchors from a markdown file (headings and explicit id/name attributes).
 */
function extractAnchors(content) {
  const anchors = new Set();
  const lines = content.split("\n");

  for (const line of lines) {
    const headingMatch = line.match(/^#{1,6}\s+(.+)$/);
    if (headingMatch) {
      const headingText = headingMatch[1].trim();
      anchors.add(slugify(headingText));
    }

    const htmlAnchorRegex = /(?:id|name)=["']([^"']+)["']/g;
    let match;
    while ((match = htmlAnchorRegex.exec(line)) !== null) {
      anchors.add(match[1]);
      anchors.add(slugify(match[1]));
    }
  }

  return anchors;
}

/**
 * Strip code blocks and inline code to prevent false positives.
 */
function removeCodeBlocks(content) {
  const fencedRe = /```[\s\S]*?```/g;
  let clean = content.replace(fencedRe, (match) => {
    const lines = match.split("\n").length - 1;
    return "\n".repeat(lines);
  });

  clean = clean.replace(/`[^`\n]+`/g, (match) => " ".repeat(match.length));
  return clean;
}

/**
 * Validate Mermaid diagrams across all Markdown files.
 */
function validateMermaidDiagrams(mdFiles) {
  const errors = [];
  let totalDiagrams = 0;

  for (const file of mdFiles) {
    const relFile = path.relative(REPO_ROOT, file);
    const content = fs.readFileSync(file, "utf8");
    const lines = content.split("\n");

    let inMermaid = false;
    let startLine = 0;
    let diagramLines = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.trim() === "```mermaid") {
        inMermaid = true;
        startLine = i + 1;
        diagramLines = [];
        totalDiagrams++;
      } else if (inMermaid && line.trim() === "```") {
        inMermaid = false;
        const text = diagramLines.join("\n");
        const firstLine = diagramLines.find(
          (l) => l.trim().length > 0 && !l.trim().startsWith("%%")
        );
        if (!firstLine) {
          errors.push({
            file: relFile,
            line: startLine,
            reason: "Empty Mermaid diagram block",
          });
          continue;
        }

        const diagType = firstLine.trim().split(/\s+/)[0];
        if (!ALLOWED_MERMAID_TYPES.has(diagType)) {
          errors.push({
            file: relFile,
            line: startLine,
            reason: `Unsupported Mermaid diagram type '${diagType}'`,
          });
        }

        const quotes = (text.match(/"/g) || []).length;
        if (quotes % 2 !== 0) {
          errors.push({
            file: relFile,
            line: startLine,
            reason: `Unbalanced quotes in Mermaid diagram (${quotes} quotes)`,
          });
        }

        for (const dLine of diagramLines) {
          // Check for unquoted parentheses inside square brackets like A[Foo (bar)]
          const match = /\w+\[([^"\]]*\([^"\]]*\)[^"\]]*)\]/.exec(dLine);
          if (match) {
            errors.push({
              file: relFile,
              line: startLine,
              reason: `Unquoted parentheses inside node bracket: '${dLine.trim()}' (quote as ["..."])`,
            });
          }
        }
      } else if (inMermaid) {
        diagramLines.push(line);
      }
    }
  }

  return { totalDiagrams, errors };
}

/**
 * Validate ADR and OQ citations against docs/12.
 */
function validateADRsAndOQs(mdFiles) {
  const errors = [];
  const docs12Path = path.join(REPO_ROOT, "docs/12-architecture-decisions-and-open-questions.md");
  if (!fs.existsSync(docs12Path)) {
    return { errors: [{ file: "docs/12", reason: "docs/12 not found" }] };
  }

  const docs12 = fs.readFileSync(docs12Path, "utf8");
  const definedAdrs = new Set([...docs12.matchAll(/### (ADR-\d+)/g)].map((m) => m[1]));
  const definedOqs = new Set([...docs12.matchAll(/\|\s*(OQ-\d+)\s*\|/g)].map((m) => m[1]));

  for (const file of mdFiles) {
    const relFile = path.relative(REPO_ROOT, file);
    const content = fs.readFileSync(file, "utf8");

    // Match all ADR citations (ADR-001 through ADR-049)
    const adrMatches = [...content.matchAll(/\bADR-(\d+)\b/g)];
    for (const match of adrMatches) {
      const num = parseInt(match[1], 10);
      const adrId = `ADR-${num.toString().padStart(3, "0")}`;
      if (!definedAdrs.has(adrId)) {
        errors.push({
          file: relFile,
          reason: `Referenced unknown ADR '${adrId}' (not defined in docs/12)`,
        });
      }
    }

    // Match all OQ citations (OQ-01 through OQ-18)
    const oqMatches = [...content.matchAll(/\bOQ-(\d+)\b/g)];
    for (const match of oqMatches) {
      const num = parseInt(match[1], 10);
      const oqId = `OQ-${num.toString().padStart(2, "0")}`;
      if (!definedOqs.has(oqId)) {
        errors.push({
          file: relFile,
          reason: `Referenced unknown OQ '${oqId}' (not defined in docs/12)`,
        });
      }
    }
  }

  return { definedAdrsCount: definedAdrs.size, definedOqsCount: definedOqs.size, errors };
}

/**
 * Validate critical brand asset inventory.
 */
function validateBrandAssets() {
  const errors = [];
  const requiredAssets = [
    "brand/brand-sheet.svg",
    "brand/svg/devmind-mark-for-dark.svg",
    "brand/svg/devmind-mark-for-light.svg",
    "brand/svg/devmind-lockup-horizontal-for-dark.svg",
    "brand/svg/devmind-lockup-horizontal-for-light.svg",
    "brand/svg/devmind-favicon.svg",
    "brand/favicon/favicon.ico",
    "brand/tokens/devmind-tokens.css",
    "brand/tokens/tokens.json",
    "brand/tokens/palette.csv",
  ];

  for (const asset of requiredAssets) {
    if (!fs.existsSync(path.join(REPO_ROOT, asset))) {
      errors.push({
        file: asset,
        reason: "Required brand identity asset missing from repository",
      });
    }
  }

  return { verifiedCount: requiredAssets.length, errors };
}

function main() {
  const mdFiles = findMarkdownFiles(REPO_ROOT);
  const anchorCache = new Map();

  for (const file of mdFiles) {
    const rawContent = fs.readFileSync(file, "utf8");
    anchorCache.set(path.resolve(file), extractAnchors(rawContent));
  }

  let totalLinks = 0;
  let brokenLinks = [];

  for (const file of mdFiles) {
    const relFile = path.relative(REPO_ROOT, file);
    const rawContent = fs.readFileSync(file, "utf8");
    const strippedContent = removeCodeBlocks(rawContent);
    const lines = strippedContent.split("\n");

    const linkRegex = /!?\[([^\]]*)\]\(([^)]+)\)/g;

    lines.forEach((line, lineIdx) => {
      let match;
      while ((match = linkRegex.exec(line)) !== null) {
        const rawUrl = match[2].trim();

        if (
          rawUrl.startsWith("http://") ||
          rawUrl.startsWith("https://") ||
          rawUrl.startsWith("mailto:") ||
          rawUrl.startsWith("vscode:") ||
          rawUrl.startsWith("tel:")
        ) {
          continue;
        }

        totalLinks++;
        const [urlPath, anchor] = rawUrl.split("#");
        const lineNumber = lineIdx + 1;

        if (!urlPath) {
          if (anchor) {
            const anchors = anchorCache.get(path.resolve(file));
            const cleanAnchor = slugify(anchor);
            if (!anchors.has(cleanAnchor) && !anchors.has(anchor)) {
              brokenLinks.push({
                file: relFile,
                line: lineNumber,
                link: rawUrl,
                reason: `Anchor '#${anchor}' not found in current document`,
              });
            }
          }
          continue;
        }

        const targetPath = path.resolve(path.dirname(file), urlPath);

        if (!fs.existsSync(targetPath)) {
          brokenLinks.push({
            file: relFile,
            line: lineNumber,
            link: rawUrl,
            reason: `Target file not found: '${path.relative(REPO_ROOT, targetPath)}'`,
          });
          continue;
        }

        const stat = fs.statSync(targetPath);
        if (stat.isDirectory()) {
          const hasReadme =
            fs.existsSync(path.join(targetPath, "README.md")) ||
            fs.existsSync(path.join(targetPath, "index.md"));
          if (!hasReadme && !anchor) {
            // Permissible directory reference
          }
        } else if (anchor && targetPath.endsWith(".md")) {
          let targetAnchors = anchorCache.get(targetPath);
          if (!targetAnchors) {
            targetAnchors = extractAnchors(fs.readFileSync(targetPath, "utf8"));
            anchorCache.set(targetPath, targetAnchors);
          }

          const cleanAnchor = slugify(anchor);
          if (!targetAnchors.has(cleanAnchor) && !targetAnchors.has(anchor)) {
            brokenLinks.push({
              file: relFile,
              line: lineNumber,
              link: rawUrl,
              reason: `Anchor '#${anchor}' not found in target file '${path.relative(REPO_ROOT, targetPath)}'`,
            });
          }
        }

        if (VERBOSE) {
          console.log(`  ✓ [${relFile}:${lineNumber}] -> ${rawUrl}`);
        }
      }
    });
  }

  // Run additional audit checks
  const mermaidAudit = validateMermaidDiagrams(mdFiles);
  const adrOqAudit = validateADRsAndOQs(mdFiles);
  const brandAudit = validateBrandAssets();

  console.log(`\n========================================`);
  console.log(`DevMind Documentation & Brand Audit`);
  console.log(`========================================`);
  console.log(`Scanned ${mdFiles.length} Markdown files.`);
  console.log(`Checked ${totalLinks} relative links & anchors.`);
  console.log(`Validated ${mermaidAudit.totalDiagrams} Mermaid diagrams.`);
  console.log(
    `Verified ${adrOqAudit.definedAdrsCount} ADRs and ${adrOqAudit.definedOqsCount} OQ references.`
  );
  console.log(`Verified ${brandAudit.verifiedCount} brand identity assets.`);

  const allFailures = [
    ...brokenLinks.map((b) => `[Link] ${b.file}:${b.line} -> ${b.link} (${b.reason})`),
    ...mermaidAudit.errors.map((e) => `[Mermaid] ${e.file}:${e.line} (${e.reason})`),
    ...adrOqAudit.errors.map((e) => `[ADR/OQ] ${e.file} (${e.reason})`),
    ...brandAudit.errors.map((e) => `[Brand] ${e.file} (${e.reason})`),
  ];

  if (allFailures.length === 0) {
    console.log(
      `\n✓ All documentation links, anchors, Mermaid diagrams, ADR/OQ references, and brand assets are valid.\n`
    );
    process.exit(0);
  } else {
    console.error(`\n✗ Found ${allFailures.length} audit issue(s):\n`);
    for (const f of allFailures) {
      console.error(`  - ${f}`);
    }
    console.error(``);
    process.exit(1);
  }
}

main();
