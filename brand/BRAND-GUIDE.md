# DevMind Brand Guide

**Purpose.** How to use the DevMind logo, colors and type, and what every file in this folder is for. The visual system itself (tokens, screens, motion) is specified in [docs/08-ui-ux-design-specification.md](../docs/08-ui-ux-design-specification.md); this guide covers the identity assets built on it.

**Status.** Proposed identity, produced from the specification. A human should review it against the design review gate (docs/08 §18). No trademark or logo-similarity search has been done; do that before public launch.

---

## 1. The idea

The mark is a **D that contains an M**: *Dev* holding *Mind*.

| Part | Meaning |
|---|---|
| **D** (off-white) | The editor pane. The straight stem on the left is the line-number gutter, the same gutter the website layout is built around ([08](../docs/08-ui-ux-design-specification.md) §3.1). The round bowl is also a hemisphere: a mind. |
| **M** (blue graph) | A path of connected nodes shaped like an M. It stands for the shared Project Brain: code, symbols, bugs, docs and findings linked by relationships. Blue means *connection*. |
| **Center node** (green, with ring) | The evidence at the center of the graph. Every answer and every finding points back to something real. Green means *verified, active*. |
| **The i in the wordmark** | The same green node replaces the dot of the *i* in "DevMind", so the wordmark carries the mark's idea. |

It deliberately avoids generic AI imagery (sparkles, brains, robots, glowing orbs). Square corners, a flat fill, and a gutter-shaped stem keep it code-native.

## 2. Logo versions

| Version | Use | Files |
|---|---|---|
| **Mark** | Avatars, app icons, small spaces | `svg/devmind-mark-for-dark.svg`, `…-for-light.svg` |
| **Horizontal lockup** | Default for headers, docs, slides | `svg/devmind-lockup-horizontal-for-dark.svg`, `…-for-light.svg` |
| **Stacked lockup** | Square or tall spaces, covers | `svg/devmind-lockup-stacked-for-dark.svg`, `…-for-light.svg` |
| **Wordmark** | Rare; only when the mark is shown nearby | `svg/devmind-wordmark-for-dark.svg`, `…-for-light.svg` |
| **App icon** | Rounded tile on dark or light | `svg/devmind-icon-dark.svg`, `…-light.svg`, `…-fullbleed-dark.svg` |
| **Favicon mark** | 16 to 48 px only (simplified: D plus one node) | `svg/devmind-favicon.svg` |
| **Mono** (white or black) | Single-color print, stamps, watermarks, GitHub README on unknown backgrounds | `svg/devmind-mark-mono-*.svg`, `devmind-lockup-horizontal-mono-*.svg` |
| **Animated mark** | Loading or intro on the website; plays once, honors reduced motion | `svg/devmind-mark-animated.svg` |

`for-dark` means the logo is meant to sit on dark surfaces (`#0B0F12` and similar); `for-light` is for light surfaces and uses deeper blue and green so contrast holds. All SVG text is converted to outlines, so no font is needed to display them.

## 3. Color

| Role | Name | Hex | Notes |
|---|---|---|---|
| Surface | Ink | `#0B0F12` | Page background; tile background |
| Logo D (dark use) | Paper | `#E8E6E1` | Warm off-white, not pure white |
| Logo M (dark use) | Reference blue | `#4EA1FF` | 7.21:1 on Ink |
| Logo node (dark use) | Signal green | `#20E3A2` | 11.52:1 on Ink |
| Logo M (light use) | Blue | `#1863C4` | 5.8:1 on white |
| Logo node (light use) | Green | `#087F59` | 5.01:1 on white |
| Light surface | Paper bg | `#F4F3EF` | |

Full palette with contrast ratios: `tokens/palette.csv`. Color is information, not decoration: green = good or active, blue = connection, amber/coral = severity. Do not use the accent colors as large fills in the interface.

## 4. Typography

| Role | Family | Where |
|---|---|---|
| Wordmark | IBM Plex Sans SemiBold, outlined, tracking −1.2% | Logo only; never retype it |
| Display | Instrument Serif | Headlines on marketing pages and report titles |
| UI | IBM Plex Sans | Interface text |
| Code and metadata | JetBrains Mono | Paths, IDs, evidence levels, labels |

All three are open-licensed (SIL OFL) per their repositories at the time of generation; confirm and self-host at implementation (OQ-16 in [12](../docs/12-architecture-decisions-and-open-questions.md)).

## 5. Clear space and minimum size

- **Clear space:** keep at least one quarter of the mark's height (32 units on its 128-unit grid) free on every side.
- **Minimum size:** mark 24 px; horizontal lockup 120 px wide; stacked lockup 96 px wide. Below 24 px use the favicon mark.
- Never place the logo on busy imagery. If a photo is unavoidable, use a solid tile behind it.

## 6. Do and don't

| Do | Don't |
|---|---|
| Use the `for-dark` files on dark surfaces and `for-light` on light | Put the dark-surface logo on a light background, or the reverse |
| Use the mono versions when only one color is available | Recolor the nodes or lines, or add gradients, glows or shadows |
| Keep proportions; scale uniformly | Stretch, rotate, outline, or animate the mark on a loop |
| Use the favicon mark below 24 px | Shrink the full mark until the M turns to mush |
| Show the wordmark with its green *i* | Retype "DevMind" in another font |

## 7. File inventory

| Folder | Contents |
|---|---|
| `brand-sheet.png` / `.svg` | One-page overview of the identity |
| `svg/` | Master vector files (15 logo files plus wordmarks) |
| `png/` | Marks (128 to 1024 px), icons (64 to 1024 px), lockups (1200 and 2400 px wide), with transparent backgrounds except the `…-bg-` files |
| `favicon/` | `favicon.ico` (16, 32, 48), `favicon.svg`, PNG favicons, `apple-touch-icon.png` (180), Android icons (192, 512), `maskable-icon-512x512.png`, `safari-pinned-tab.svg`, `site.webmanifest`, `head-snippet.html` |
| `social/` | `og-image-1200x630.png`, `github-social-preview-1280x640.png`, `avatar-400.png`, `avatar-square-1024.png` |
| `vscode/` | `icon.png` (128, Marketplace icon), `icon@2x.png` (256), `activitybar-icon.svg` (monochrome, follows the theme) |
| `tokens/` | `devmind-tokens.css`, `tokens.json`, `tailwind.preset.cjs`, `palette.csv` |
| `source/` | `lib.py` and `build.py` regenerate every file (needs `cairosvg`, `Pillow`, `fonttools`, and the three fonts) |

## 8. How to apply it

### Website (Next.js, docs/08 §17)

1. Copy `tokens/devmind-tokens.css` to `client/app/` as `tokens.css` and import it once in the root layout; extend Tailwind with `tokens/tailwind.preset.cjs`.
2. Put `favicon/*` and `social/og-image-1200x630.png` in `client/public/`, and use `favicon/head-snippet.html` as the reference for metadata.
3. Use `svg/devmind-lockup-horizontal-for-dark.svg` in the app shell header and `devmind-mark-for-dark.svg` for the gutter rail.

### VS Code extension (docs/06 §9, §18)

In `package.json`:

```json
{
  "icon": "media/icon.png",
  "galleryBanner": { "color": "#0B0F12", "theme": "dark" },
  "contributes": {
    "viewsContainers": {
      "activitybar": [{ "id": "devmind", "title": "DevMind", "icon": "media/activitybar-icon.svg" }]
    }
  }
}
```

Copy `vscode/icon.png` and `vscode/activitybar-icon.svg` into `extension/media/`. The activity-bar icon uses `currentColor`, so VS Code themes it automatically.

### GitHub and social

Upload `social/github-social-preview-1280x640.png` as the repository social preview and `social/avatar-400.png` as the organization or profile avatar.

## 9. Open items

- Trademark and similarity search before public launch.
- Font licenses confirmed and self-hosted (OQ-16).
- Human visual review against docs/08 §18, including a squint test of the favicon at 16 px on real browser tabs.
- The `for-light` colors were chosen for contrast; review them on real light surfaces before print use.
