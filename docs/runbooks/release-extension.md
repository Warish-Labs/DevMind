# release-extension.md

How to publish the DevMind VS Code extension to the Visual Studio Marketplace and Open VSX.

**Publisher id:** `WarishLabs`  
**Marketplace URL:** [https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode](https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode)  
**Install command:** `ext install WarishLabs.devmind-vscode`

---

## Prerequisites

1. **VS Marketplace**: A publisher account at `marketplace.visualstudio.com` under the id `WarishLabs`.
2. **Azure DevOps PAT** (VS Marketplace): Required for `vsce publish`.
   - Note: Global Azure DevOps PATs retire **2026-12-01**. After that date, use `vsce publish --azure-credential` with a federated credential or scoped PAT. Document the migration in this file before that date.
   - How to create: dev.azure.com → User Settings → Personal Access Tokens → New Token → Marketplace (Manage) scope.
3. **Open VSX token**: open-vsx.org → User Settings → Access Tokens.
4. GitHub Secrets in the `extension-release` environment:
   - `VSCE_PAT` — Azure DevOps PAT for VS Marketplace
   - `OVSX_PAT` — Open VSX access token

---

## Local test before publishing

```bash
# Build the extension
pnpm --filter extension build

# Create a .vsix package
pnpm --filter extension package

# Verify the package contents
pnpm --filter extension vsce ls

# Install locally to test
code --install-extension extension/devmind-0.0.1.vsix
```

The `.vsix` file is git-ignored. Never commit it.

---

## CI release flow

1. Create a git tag: `git tag ext-v0.1.0 && git push origin ext-v0.1.0`
2. The `release-extension.yml` workflow runs automatically:
   - Builds and tests the extension.
   - Runs `vsce package` to produce a `.vsix`.
   - Uploads the `.vsix` as a workflow artifact.
   - Creates a draft GitHub Release with the `.vsix` attached.
   - Two publish jobs run in the `extension-release` environment (requires manual approval):
     - Publish to VS Marketplace (`vsce publish`)
     - Publish to Open VSX (`ovsx publish`)
3. Owner reviews the draft Release and approves the `extension-release` environment in GitHub.
4. Extension goes live on both marketplaces.

When `VSCE_PAT` or `OVSX_PAT` secrets are absent, the publish jobs are skipped (not failed).

---

## Extension marketplace listing requirements

- `icon`: `media/icon.png` (128×128, from `brand/vscode/icon.png`)
- `galleryBanner`: `{ "color": "#0B0F12", "theme": "dark" }`
- `README.md` in `extension/`: marketplace listing page; must include screenshots and honest status
- `CHANGELOG.md`: Keep a Changelog format
- `LICENSE`: placeholder until owner decides license
- `repository` field in `package.json`: `https://github.com/Warish-Labs/DevMind`
- `categories`: `["Other"]` initially; add `["Linters", "Programming Languages"]` after M3

---

## Pre-release flag

For early access before MVP: publish with `--pre-release` flag. Users can opt in to pre-release versions in the Marketplace UI.

---

## Azure credential migration (before 2026-12-01)

When global Azure DevOps PATs are retired:
1. Update the `release-extension.yml` workflow to use `vsce publish --azure-credential`.
2. Set up a federated credential or use a scoped PAT per the current VS Code docs.
3. Update this runbook with the new steps.
4. Record the change in `docs/12-architecture-decisions-and-open-questions.md`.
