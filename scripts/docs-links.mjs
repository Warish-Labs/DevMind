#!/usr/bin/env node

/**
 * scripts/docs-links.mjs
 * Validates relative links and anchor fragments across all Markdown files in the repository.
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
    // Check headings #, ##, etc.
    const headingMatch = line.match(/^#{1,6}\s+(.+)$/);
    if (headingMatch) {
      const headingText = headingMatch[1].trim();
      anchors.add(slugify(headingText));
    }

    // Check HTML anchors: <a name="..."> or <a id="..."> or any element with id="..."
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
  // Replace code blocks with whitespace of identical line count to preserve line numbers
  const fencedRe = /```[\s\S]*?```/g;
  let clean = content.replace(fencedRe, (match) => {
    const lines = match.split("\n").length - 1;
    return "\n".repeat(lines);
  });

  // Replace inline code with empty spaces
  clean = clean.replace(/`[^`\n]+`/g, (match) => " ".repeat(match.length));
  return clean;
}

function main() {
  const mdFiles = findMarkdownFiles(REPO_ROOT);
  const anchorCache = new Map();

  // Pre-index anchors for all markdown files
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

        // Ignore web / external protocol links
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

        // Internal anchor link within the same file (#heading)
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

        // Relative path link (with or without anchor)
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

        // If target is a directory, check for README.md or index.md
        const stat = fs.statSync(targetPath);
        if (stat.isDirectory()) {
          const hasReadme =
            fs.existsSync(path.join(targetPath, "README.md")) ||
            fs.existsSync(path.join(targetPath, "index.md"));
          if (!hasReadme && !anchor) {
            // Permissible directory reference if folder exists
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

  console.log(`\n========================================`);
  console.log(`DevMind Documentation Link Check`);
  console.log(`========================================`);
  console.log(`Scanned ${mdFiles.length} Markdown files.`);
  console.log(`Checked ${totalLinks} relative links & anchors.`);

  if (brokenLinks.length === 0) {
    console.log(`\n✓ All relative documentation links and anchors are valid.\n`);
    process.exit(0);
  } else {
    console.error(`\n✗ Found ${brokenLinks.length} broken link(s):\n`);
    for (const b of brokenLinks) {
      console.error(`  - ${b.file}:${b.line} -> ${b.link}`);
      console.error(`    Reason: ${b.reason}`);
    }
    console.error(``);
    process.exit(1);
  }
}

main();
