import esbuild from "esbuild";
import process from "node:process";

const args = process.argv.slice(2);
const isWatch = args.includes("--watch");
const isProduction = args.includes("--production");

async function main() {
  const context = await esbuild.context({
    entryPoints: ["src/extension.ts"],
    bundle: true,
    format: "cjs",
    minify: isProduction,
    sourcemap: !isProduction,
    sourcesContent: false,
    platform: "node",
    outfile: "dist/extension.js",
    external: ["vscode"],
    logLevel: "info",
  });

  if (isWatch) {
    console.log("[esbuild] Watching extension files for changes...");
    await context.watch();
  } else {
    await context.rebuild();
    await context.dispose();
    console.log("[esbuild] Build complete: dist/extension.js");
  }
}

main().catch((err) => {
  console.error("[esbuild] Build failed:", err);
  process.exit(1);
});
