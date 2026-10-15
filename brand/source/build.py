import os, sys, json, csv, io, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cairosvg
from PIL import Image
from lib import *

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for d in ["svg", "png", "favicon", "social", "vscode", "tokens", "source"]:
    os.makedirs(f"{OUT}/{d}", exist_ok=True)


def w(path, s):
    with open(f"{OUT}/{path}", "w") as fh:
        fh.write(s)


def png(svg, path, width=None, height=None, bg=None):
    cairosvg.svg2png(bytestring=svg.encode(), write_to=f"{OUT}/{path}", output_width=width,
                     output_height=height, background_color=bg)


WHITE = mono("#FFFFFF")
BLACK = mono("#0B0F12")

# ------------------------------------------------------------------ SVG set
svgs = {
    "devmind-mark-for-dark": mark_svg(DARK),
    "devmind-mark-for-light": mark_svg(LIGHT),
    "devmind-mark-mono-white": mark_svg(WHITE),
    "devmind-mark-mono-black": mark_svg(BLACK),
    "devmind-mark-animated": animated_mark(DARK),
    "devmind-icon-dark": app_icon(DARK),
    "devmind-icon-light": app_icon(LIGHT),
    "devmind-icon-fullbleed-dark": app_icon(DARK, rounded=False, scale=0.78),
    "devmind-favicon": favicon_svg(DARK),
    "devmind-lockup-horizontal-for-dark": lockup_h(DARK, bg=False)[0],
    "devmind-lockup-horizontal-for-light": lockup_h(LIGHT, bg=False)[0],
    "devmind-lockup-horizontal-mono-white": lockup_h(WHITE, bg=False)[0],
    "devmind-lockup-horizontal-mono-black": lockup_h(BLACK, bg=False)[0],
    "devmind-lockup-stacked-for-dark": lockup_v(DARK, bg=False)[0],
    "devmind-lockup-stacked-for-light": lockup_v(LIGHT, bg=False)[0],
}
for name, s in svgs.items():
    w(f"svg/{name}.svg", s)

# wordmark only
for tag, c in (("for-dark", DARK), ("for-light", LIGHT)):
    ch = cap_height(PLEX_SB, 84)
    wm, ww = wordmark(c, 84, 0, ch + 6)
    w(f"svg/devmind-wordmark-{tag}.svg", wrap(wm, ww, ch + 6 + 4, None, 12))

# ------------------------------------------------------------------ PNG set
# marks (transparent)
for size in (128, 256, 512, 1024):
    png(svgs["devmind-mark-for-dark"], f"png/devmind-mark-for-dark-{size}.png", size, size)
    png(svgs["devmind-mark-for-light"], f"png/devmind-mark-for-light-{size}.png", size, size)
png(svgs["devmind-mark-mono-white"], "png/devmind-mark-mono-white-512.png", 512, 512)
png(svgs["devmind-mark-mono-black"], "png/devmind-mark-mono-black-512.png", 512, 512)
# icons
for size in (64, 128, 192, 256, 512, 1024):
    png(svgs["devmind-icon-dark"], f"png/devmind-icon-dark-{size}.png", size, size)
for size in (256, 512, 1024):
    png(svgs["devmind-icon-light"], f"png/devmind-icon-light-{size}.png", size, size)
# lockups
for key in ("horizontal-for-dark", "horizontal-for-light", "stacked-for-dark", "stacked-for-light",
            "horizontal-mono-white", "horizontal-mono-black"):
    s = svgs[f"devmind-lockup-{key}"]
    for width in (1200, 2400):
        png(s, f"png/devmind-lockup-{key}-{width}w.png", width)
# lockups with solid background (for places that cannot show transparency)
s, _, _ = lockup_h(DARK, bg=True)
png(s, "png/devmind-lockup-horizontal-dark-bg-1200w.png", 1200)
s, _, _ = lockup_h(LIGHT, bg=True)
png(s, "png/devmind-lockup-horizontal-light-bg-1200w.png", 1200)

# ------------------------------------------------------------------ favicon / app icons
fav = svgs["devmind-favicon"]
for size in (16, 32, 48):
    png(fav, f"favicon/favicon-{size}x{size}.png", size, size)
png(svgs["devmind-icon-fullbleed-dark"], "favicon/apple-touch-icon.png", 180, 180)
png(svgs["devmind-icon-dark"], "favicon/android-chrome-192x192.png", 192, 192)
png(svgs["devmind-icon-dark"], "favicon/android-chrome-512x512.png", 512, 512)
# maskable: full bleed, mark kept inside the 80% safe zone
png(app_icon(DARK, rounded=False, scale=0.62), "favicon/maskable-icon-512x512.png", 512, 512)
w("favicon/favicon.svg", fav)
w("favicon/safari-pinned-tab.svg", mark_svg(BLACK))
base = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=fav.encode(), output_width=256, output_height=256))).convert("RGBA")
base.save(f"{OUT}/favicon/favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
w("favicon/site.webmanifest", json.dumps({
    "name": "DevMind", "short_name": "DevMind",
    "description": "Agentic AI software engineering for your whole project lifecycle.",
    "icons": [
        {"src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/maskable-icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    "theme_color": "#0B0F12", "background_color": "#0B0F12", "display": "standalone"}, indent=2) + "\n")
w("favicon/head-snippet.html", """<!-- Place the files in the web root (Next.js: /public, or app/ for icon.* conventions) -->
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="mask-icon" href="/safari-pinned-tab.svg" color="#0B0F12">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#0B0F12">
<meta property="og:image" content="/og-image-1200x630.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
""")

# ------------------------------------------------------------------ VS Code extension icon
png(svgs["devmind-icon-dark"], "vscode/icon.png", 128, 128)
png(svgs["devmind-icon-dark"], "vscode/icon@2x.png", 256, 256)
# the VS Code activity bar needs a monochrome icon that follows the theme (currentColor)
act = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" '
       'stroke-width="1.8" stroke-linejoin="miter"><path d="M5 4.5H11.5A7.5 7.5 0 0 1 11.5 19.5H5Z"/>'
       '<polyline points="8.5,15 8.5,9 12,12.5 15.5,9 15.5,15" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"/>'
       '</svg>')
w("vscode/activitybar-icon.svg", act)

# ------------------------------------------------------------------ social images
def og(Wd, Hd, name):
    oy = (Hd - 630) / 2
    fg0, fg1, fg2 = "#E8E6E1", "#A9B0B6", "#7C858D"
    parts = [f'<rect width="1200" height="{Hd}" fill="#0B0F12"/>']
    # gutter
    parts.append(f'<line x1="92" y1="0" x2="92" y2="{Hd}" stroke="#232B33" stroke-width="2"/>')
    n = 1
    y = 52 + oy % 36
    while y < Hd:
        t, tw = text_svg(MONO, str(n), 15, 0, 0, fg2, wght=400)
        # right-align at x=70
        t, _ = text_svg(MONO, str(n), 15, 70 - tw, y, fg2, wght=400)
        parts.append(f'<g opacity="0.45">{t}</g>')
        n += 1
        y += 36
    # lockup
    lk, lw, lh = lockup_h(DARK, bg=False, pad=0)
    sc = 0.56
    parts.append(f'<g transform="translate(128 {64 + oy:.1f}) scale({sc})">{mark(DARK)}'
                 + wordmark(DARK, 84, 128 + 22, 64 + cap_height(PLEX_SB, 84) / 2)[0] + '</g>')
    # headline
    h1, _ = text_svg(SERIF, "Know what your", 78, 128, 300 + oy, fg0)
    h2, _ = text_svg(SERIF, "code actually allows.", 78, 128, 386 + oy, fg0)
    parts += [h1, h2]
    foot, _ = text_svg(MONO, "@@ evidence-backed findings · local-first scanning @@", 19, 128, 560 + oy, fg2, wght=500)
    parts.append(foot)
    # margin-note card (mirrors the homepage Trace)
    cx, cy, cw, ch = 764, 214 + oy, 376, 214
    parts.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" fill="#10151A" stroke="#2F3944" stroke-width="2"/>')
    parts.append(f'<rect x="{cx}" y="{cy}" width="4" height="{ch}" fill="#4EA1FF"/>')
    t, _ = text_svg(MONO, "@@ /admin/users @@", 17, cx + 28, cy + 40, fg2, wght=500); parts.append(t)
    rows = [("Authentication", "required", "ok"), ("Authorization", "missing", "x")]
    ry = cy + 88
    for lab, val, kind in rows:
        t, _ = text_svg(PLEX_RG, lab, 20, cx + 28, ry, fg1); parts.append(t)
        if kind == "ok":
            parts.append(f'<path d="M{cx+198} {ry-8} l6 6 l11 -13" fill="none" stroke="#20E3A2" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
            col = "#20E3A2"
        else:
            parts.append(f'<path d="M{cx+199} {ry-16} l13 13 M{cx+212} {ry-16} l-13 13" fill="none" stroke="#FF6B5E" stroke-width="3" stroke-linecap="round"/>')
            col = "#FF6B5E"
        t, _ = text_svg(PLEX_MD, val, 20, cx + 228, ry, col); parts.append(t)
        ry += 44
    t, _ = text_svg(PLEX_RG, "Evidence", 20, cx + 28, ry + 6, fg1); parts.append(t)
    for i in range(4):
        fill = fg0 if i < 2 else "#2F3944"
        parts.append(f'<rect x="{cx+144+i*14}" y="{ry-12}" width="10" height="18" fill="{fill}"/>')
    t, _ = text_svg(MONO, "E1 · Possible", 17, cx + 214, ry + 5, fg0, wght=500); parts.append(t)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {Hd}" width="1200" height="{Hd}">'
           + "".join(parts) + "</svg>")
    png(svg, f"social/{name}.png", Wd, Hd * Wd // 1200 if Wd == 1200 else Hd)
    return svg


og_svg = og(1200, 630, "og-image-1200x630")
w("social/og-image-1200x630.svg", og_svg)
# GitHub social preview: 1280x640
gh = og(1200, 600, "github-social-preview-tmp")
png(gh, "social/github-social-preview-1280x640.png", 1280, 640)
os.remove(f"{OUT}/social/github-social-preview-tmp.png")
# avatars
png(svgs["devmind-icon-dark"], "social/avatar-400.png", 400, 400)
png(app_icon(DARK, rounded=False, scale=0.74), "social/avatar-square-1024.png", 1024, 1024)

# ------------------------------------------------------------------ tokens
def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def lum(h):
    h = h.lstrip("#"); r, g, b = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

def cr(a, b):
    la, lb = lum(a), lum(b)
    if la < lb: la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)

palette = [
    ("--bg-0", "Ink", "#0B0F12", "Page background"),
    ("--bg-1", "Panel", "#10151A", "Panels, sidebars"),
    ("--bg-2", "Raised", "#161C22", "Raised surfaces, inputs, code"),
    ("--line-1", "Hairline", "#232B33", "Decorative hairlines"),
    ("--line-2", "Border", "#2F3944", "Panel borders"),
    ("--line-3", "Control line", "#5F6C78", "Control boundaries (3:1 on all surfaces)"),
    ("--fg-0", "Paper", "#E8E6E1", "Primary text; logo D"),
    ("--fg-1", "Mist", "#A9B0B6", "Secondary text"),
    ("--fg-2", "Slate", "#7C858D", "Tertiary text, metadata"),
    ("--signal", "Signal green", "#20E3A2", "Verified, active, pass; logo evidence node"),
    ("--ref", "Reference blue", "#4EA1FF", "References, links, focus; logo M graph"),
    ("--warn", "Caution amber", "#F0B44C", "Medium severity"),
    ("--danger", "Alert coral", "#FF6B5E", "Critical and high severity"),
    ("--brand-light-bg", "Paper bg", "#F4F3EF", "Light backgrounds for logo use"),
    ("--brand-blue-on-light", "Blue (light)", "#1863C4", "Logo M on light backgrounds"),
    ("--brand-green-on-light", "Green (light)", "#087F59", "Logo node on light backgrounds"),
]
rows = []
for tok, name, hx, role in palette:
    r, g, b = [int(hx[i:i + 2], 16) for i in (1, 3, 5)]
    rows.append([tok, name, hx, f"{r},{g},{b}", role, f"{cr(hx,'#0B0F12'):.2f}", f"{cr(hx,'#FFFFFF'):.2f}"])
buf = io.StringIO()
cw = csv.writer(buf)
cw.writerow(["token", "name", "hex", "rgb", "role", "contrast_on_#0B0F12", "contrast_on_#FFFFFF"])
cw.writerows(rows)
w("tokens/palette.csv", buf.getvalue())

css = """/* DevMind design tokens. Source of truth: docs/08-ui-ux-design-specification.md sections 3 to 7.
   Copy into client/ as tokens.css. No hard-coded hex in components: use these variables. */
:root {
  /* surfaces */
  --bg-0: #0B0F12;  --bg-1: #10151A;  --bg-2: #161C22;
  /* lines (line-1/2 decorative only; line-3 for control boundaries) */
  --line-1: #232B33;  --line-2: #2F3944;  --line-3: #5F6C78;
  /* text */
  --fg-0: #E8E6E1;  --fg-1: #A9B0B6;  --fg-2: #7C858D;
  /* accents: signal = good/active, ref = connection/focus */
  --signal: #20E3A2;  --ref: #4EA1FF;  --warn: #F0B44C;  --danger: #FF6B5E;
  /* typography (self-host; confirm licences, OQ-16) */
  --font-display: "Instrument Serif", "Iowan Old Style", Georgia, serif;
  --font-ui: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  /* spacing (4px base) */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 24px;
  --space-6: 32px; --space-7: 48px; --space-8: 64px; --space-9: 96px;
  /* shape */
  --radius-chip: 2px; --radius-control: 4px; --radius-panel: 6px;
  /* motion */
  --dur-1: 90ms; --dur-2: 160ms; --dur-3: 240ms; --dur-4: 400ms; --dur-story: 800ms;
  --ease-out: cubic-bezier(0.2, 0, 0, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-move: cubic-bezier(0.4, 0, 0.2, 1);
  /* focus */
  --focus-ring: 2px solid var(--ref);
  --focus-offset: 2px;
  color-scheme: dark;
}
html { background: var(--bg-0); color: var(--fg-0); font-family: var(--font-ui); }
:focus-visible { outline: var(--focus-ring); outline-offset: var(--focus-offset); }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
"""
w("tokens/devmind-tokens.css", css)

tokens = {
    "color": {k.lstrip("-"): hx for k, _, hx, _ in palette},
    "font": {"display": "Instrument Serif", "ui": "IBM Plex Sans", "mono": "JetBrains Mono"},
    "space": [4, 8, 12, 16, 24, 32, 48, 64, 96],
    "radius": {"chip": 2, "control": 4, "panel": 6},
    "motion": {"dur1": 90, "dur2": 160, "dur3": 240, "dur4": 400,
               "easeOut": "cubic-bezier(0.2,0,0,1)", "easeIn": "cubic-bezier(0.4,0,1,1)", "easeMove": "cubic-bezier(0.4,0,0.2,1)"},
    "breakpoints": {"sm": 640, "md": 768, "lg": 1024, "xl": 1280},
}
w("tokens/tokens.json", json.dumps(tokens, indent=2) + "\n")

w("tokens/tailwind.preset.cjs", """// Tailwind preset that reads the CSS variables in devmind-tokens.css (Tailwind v3-style config).
// For Tailwind v4, map the same variables inside an @theme block instead. [VERIFY at implementation]
module.exports = {
  theme: {
    extend: {
      colors: {
        bg: { 0: "var(--bg-0)", 1: "var(--bg-1)", 2: "var(--bg-2)" },
        line: { 1: "var(--line-1)", 2: "var(--line-2)", 3: "var(--line-3)" },
        fg: { 0: "var(--fg-0)", 1: "var(--fg-1)", 2: "var(--fg-2)" },
        signal: "var(--signal)", ref: "var(--ref)", warn: "var(--warn)", danger: "var(--danger)",
      },
      fontFamily: { display: "var(--font-display)", sans: "var(--font-ui)", mono: "var(--font-mono)" },
      borderRadius: { chip: "var(--radius-chip)", control: "var(--radius-control)", panel: "var(--radius-panel)" },
      transitionDuration: { 1: "var(--dur-1)", 2: "var(--dur-2)", 3: "var(--dur-3)", 4: "var(--dur-4)" },
      transitionTimingFunction: { out: "var(--ease-out)", in: "var(--ease-in)", move: "var(--ease-move)" },
    },
  },
};
""")

# ------------------------------------------------------------------ brand sheet
def sheet():
    W, H = 1600, 1180
    fg0, fg1, fg2 = "#E8E6E1", "#A9B0B6", "#7C858D"
    P = [f'<rect width="{W}" height="{H}" fill="#0B0F12"/>']
    def T(txt, size, x, y, fill=fg0, font=PLEX_RG, wght=None):
        s, _ = text_svg(font, txt, size, x, y, fill, wght=wght); P.append(s)
    T("@@ DevMind brand sheet @@", 18, 64, 62, fg2, MONO, 500)
    # primary mark
    P.append(f'<g transform="translate(64 96) scale(3.1)">{mark(DARK)}</g>')
    T("The mark", 34, 520, 150, fg0, SERIF)
    notes = [("D", "Dev. The editor pane; the stem is the line-number gutter."),
             ("M", "Mind. A graph of connected nodes: the shared Project Brain."),
             ("Green node", "The evidence at the centre. Every answer points back to it."),
             ("Blue lines", "Relationships and references between code, bugs, docs and findings.")]
    y = 215
    for k, v in notes:
        T(k, 21, 520, y, "#20E3A2" if "Green" in k else ("#4EA1FF" if "Blue" in k else fg0), PLEX_SB)
        T(v, 21, 520 + 150, y, fg1)
        y += 46
    T("The same node becomes the dot of the i in the wordmark.", 21, 520, y + 14, fg2)
    # icons row
    T("Icons", 34, 64, 540, fg0, SERIF)
    x = 64
    for svg_s, lab in ((svgs["devmind-icon-dark"], "App icon, dark"), (svgs["devmind-icon-light"], "App icon, light")):
        inner = svg_s.split(">", 1)[1].rsplit("</svg>", 1)[0]
        P.append(f'<g transform="translate({x} 570) scale(1.25)">{inner}</g>')
        T(lab, 16, x, 752, fg2, MONO, 500)
        x += 190
    # mono tiles
    P.append('<rect x="444" y="570" width="160" height="160" rx="22" fill="#161C22" stroke="#2F3944" stroke-width="2"/>')
    P.append(f'<g transform="translate(464 590) scale(1)">{mark(WHITE)}</g>')
    T("Mono white", 16, 444, 752, fg2, MONO, 500)
    P.append('<rect x="634" y="570" width="160" height="160" rx="22" fill="#F4F3EF"/>')
    P.append(f'<g transform="translate(654 590) scale(1)">{mark(BLACK)}</g>')
    T("Mono black", 16, 634, 752, fg2, MONO, 500)
    # favicon scale
    P.append('<rect x="824" y="570" width="160" height="160" rx="22" fill="#10151A" stroke="#2F3944" stroke-width="2"/>')
    for sz, fx in ((64, 840), (32, 920), (16, 960)):
        inner = favicon_svg().split(">", 1)[1].rsplit("</svg>", 1)[0]
        P.append(f'<g transform="translate({fx} {650 - sz/2 + (0 if sz==64 else 0)}) scale({sz/32})">{inner}</g>')
    T("Favicon 64/32/16", 16, 824, 752, fg2, MONO, 500)
    # lockups
    T("Lockups", 34, 1050, 540, fg0, SERIF)
    lk_d, lw, lh = lockup_h(DARK, bg=False, pad=0)
    P.append(f'<rect x="1050" y="570" width="486" height="110" fill="#10151A" stroke="#2F3944" stroke-width="2"/>')
    P.append(f'<svg x="1074" y="590" width="{lw*70/lh:.0f}" height="70" viewBox="0 0 {lw:.1f} {lh:.1f}">{lk_d.split(">",1)[1].rsplit("</svg>",1)[0]}</svg>')
    lk_l, lw, lh = lockup_h(LIGHT, bg=False, pad=0)
    P.append(f'<rect x="1050" y="696" width="486" height="110" fill="#F4F3EF"/>')
    P.append(f'<svg x="1074" y="716" width="{lw*70/lh:.0f}" height="70" viewBox="0 0 {lw:.1f} {lh:.1f}">{lk_l.split(">",1)[1].rsplit("</svg>",1)[0]}</svg>')
    # palette
    T("Palette", 34, 64, 880, fg0, SERIF)
    sw = [("Ink", "#0B0F12"), ("Panel", "#10151A"), ("Raised", "#161C22"), ("Paper", "#E8E6E1"),
          ("Signal", "#20E3A2"), ("Reference", "#4EA1FF"), ("Caution", "#F0B44C"), ("Alert", "#FF6B5E")]
    x = 64
    for nm, hx in sw:
        P.append(f'<rect x="{x}" y="910" width="170" height="110" fill="{hx}" stroke="#2F3944" stroke-width="2"/>')
        T(nm, 19, x, 1056, fg0, PLEX_MD)
        T(hx, 16, x, 1082, fg2, MONO, 500)
        x += 188
    T("Color is information: signal = good or active, reference = connection, amber and coral = severity. Never decoration.", 18, 64, 1130, fg2)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">' + "".join(P) + "</svg>"
    w("brand-sheet.svg", svg)
    png(svg, "../brand/brand-sheet.png", W, H)


sheet()
print("built")
