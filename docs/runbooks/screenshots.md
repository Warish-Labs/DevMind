# screenshots.md

How to take screenshots for the DevMind repository. Generated screenshots live in
`docs/assets/screenshots/` (git-tracked, compressed). This document covers both the home
page screenshots (Phase S1) and the extension screenshots (Phase S2).

---

## Home page screenshots (Phase S1)

Run `pnpm screenshots` after the S1 branch is merged. This runs a Playwright script that
generates deterministic PNGs at the specified viewport sizes.

### Generated files

| File | Viewport | Description |
|---|---|---|
| `home-hero-desktop.png` | 1440×900 | Hero after sequence completes |
| `home-hero-mid-sequence.png` | 1440×900 | Hero mid-animation (step 4/7) |
| `home-brain-selected.png` | 1440×900 | Section 03 with a Brain layer selected |
| `home-walkthrough-step.png` | 1440×900 | Section 05 walkthrough at step 7 |
| `home-privacy-ledger.png` | 1440×900 | Section 07 privacy ledger, indexed mode |
| `home-cursor-cta.png` | 1440×900 | Section 08 CTA with cursor visible |
| `home-hero-mobile.png` | 390×844 | Hero on mobile |
| `home-hero-tablet.png` | 768×1024 | Hero on tablet |

All screenshots are taken with JavaScript enabled and reduced-motion disabled so the sequence completes.

### Compression

Sharp (pinned version) is used to compress PNGs. The `pnpm screenshots` command runs compression automatically.

---

## Extension screenshots (Phase S2)

These are taken manually in the Extension Development Host. Follow the exact steps to get consistent shots.

### Setup

1. Open VS Code with the DevMind workspace: `code /home/md-warish-ansari/Projects/DevMind`
2. Press **F5** to launch the Extension Development Host with `evals/scanner/fixtures/express-admin` as the workspace.
3. Set theme to **Dark Modern** (Command Palette → Preferences: Color Theme → Dark Modern).
4. Set zoom to **100%** (View → Appearance → Reset Zoom).
5. Window size: **1600 × 1000** pixels.
6. All views should show fixture data with the "Fixture data (example)" label.

### Screenshots to take

| File | What to show |
|---|---|
| `extension-01-findings.png` | Activity bar + Findings tree open, showing Critical/High items |
| `extension-02-squiggle.png` | Editor with a squiggle on the route + hover card showing finding |
| `extension-03-structure.png` | Project Structure tree with the missing-role marker visible |
| `extension-04-scan.png` | Scan view mid-progress + status bar showing "scanning 12/40" |
| `extension-05-sync.png` | Sync view with metadata_only mode and "what was sent" empty log |
| `extension-06-consent.png` | Consent preview webview with example files table and Cancel focused |
| `extension-07-commands.png` | Command Palette with "DevMind:" prefix and all commands listed |
| `extension-08-database.png` | Database (from files) view showing schema entities from fixture |

### Rules for extension screenshots

- All data shown is fixture/example data. The status bar must show "fixture".
- Never show real credentials, real API keys, or real user data.
- Do not show the fixture mode toggle in the "off" position.

---

## After taking screenshots

1. Compress if not done automatically (`sharp` or `optipng`).
2. Commit to `docs/assets/screenshots/`.
3. Update the README screenshot table to use the real images (not placeholder paths).
4. Update `docs/showcase/README.personal.md` with the raw GitHub URLs.
