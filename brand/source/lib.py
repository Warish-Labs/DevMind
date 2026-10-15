"""DevMind brand asset library: mark geometry, outlined text, color sets."""
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

import os
FONTS = os.environ.get("DEVMIND_FONTS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")) + "/"

# ---------------------------------------------------------------- colors
DARK = dict(bg="#0B0F12", d="#E8E6E1", m="#4EA1FF", node="#20E3A2", text="#E8E6E1",
            sub="#A9B0B6", ring_op="0.55")
LIGHT = dict(bg="#F4F3EF", d="#0B0F12", m="#1863C4", node="#087F59", text="#0B0F12",
             sub="#4A545C", ring_op="0.5")


def mono(c):
    return dict(bg=None, d=c, m=c, node=c, text=c, sub=c, ring_op="0")


# ---------------------------------------------------------------- mark
# 128 x 128 grid. D = Dev (stem = editor gutter, bowl = pane / hemisphere).
# M = Mind, drawn as a connected graph inside the D; centre node = the evidence.
D_PATH = "M27 19 H56 A45 45 0 0 1 56 109 H27 Z"
M_PTS = [(46, 84), (46, 45), (64, 67), (82, 45), (82, 84)]
M_POLY = " ".join(f"{x},{y}" for x, y in M_PTS)


def mark(c, ring=True, anim=False):
    """Return the mark as SVG elements for a 128x128 box."""
    nodes = ""
    for i, (x, y) in enumerate(M_PTS):
        if i == 2:
            continue
        nodes += f'<circle class="n" cx="{x}" cy="{y}" r="5.5" fill="{c["m"]}"/>'
    cx, cy = M_PTS[2]
    core = f'<circle class="core" cx="{cx}" cy="{cy}" r="7.5" fill="{c["node"]}"/>'
    if ring and c["ring_op"] != "0":
        core = (f'<circle class="ring" cx="{cx}" cy="{cy}" r="12" fill="none" stroke="{c["node"]}" '
                f'stroke-width="2" opacity="{c["ring_op"]}"/>') + core
    cls_d = ' class="d"' if anim else ""
    cls_m = ' class="m"' if anim else ""
    return (f'<path{cls_d} d="{D_PATH}" fill="none" stroke="{c["d"]}" stroke-width="9" stroke-linejoin="miter"/>'
            f'<polyline{cls_m} points="{M_POLY}" fill="none" stroke="{c["m"]}" stroke-width="5" '
            f'stroke-linecap="round" stroke-linejoin="round"/>' + nodes + core)


def small_mark(c):
    """Simplified favicon-scale mark on a 32 grid: D + one evidence node."""
    return (f'<path d="M6.5 5 H15 A11 11 0 0 1 15 27 H6.5 Z" fill="none" stroke="{c["d"]}" '
            f'stroke-width="3.2" stroke-linejoin="miter"/>'
            f'<circle cx="15.5" cy="16" r="3.4" fill="{c["node"]}"/>')


# ---------------------------------------------------------------- fonts
_cache = {}


def font(name, wght=None):
    key = (name, wght)
    if key not in _cache:
        f = TTFont(FONTS + name)
        if wght is not None:
            f = instancer.instantiateVariableFont(f, {"wght": wght})
        _cache[key] = f
    return _cache[key]


def _glyph_d(f, gname, x, y, s):
    gs = f.getGlyphSet()
    pen = SVGPathPen(gs)
    gs[gname].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
    return pen.getCommands()


def _tittle(f, s):
    """Return (d_without_dot, dot_cx, dot_cy, dot_r) in font units for glyph i."""
    gs = f.getGlyphSet()
    rec = DecomposingRecordingPen(gs)
    gs["i"].draw(rec)
    contours, cur = [], []
    for op, args in rec.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            contours.append(cur)
            cur = []
    info = []
    for ct in contours:
        bp = BoundsPen(gs)
        for op, args in ct:
            getattr(bp, op)(*args)
        info.append(bp.bounds)
    dot_i = max(range(len(info)), key=lambda k: info[k][1])
    b = info[dot_i]
    return contours, dot_i, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(b[2] - b[0], b[3] - b[1]) / 2)


def text_path(fontfile, text, size, x, y, wght=None, track=0.0, node_dot=None):
    """Outline `text` into one path string. Returns (svg, width).
    node_dot: colour for a circular tittle on every 'i' (replaces the glyph dot)."""
    f = font(fontfile, wght)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    s = size / upm
    cur = x
    ds, extras = [], []
    for ch in text:
        g = cmap[ord(ch)]
        if ch == "i" and node_dot:
            contours, di, (dcx, dcy, dr) = _tittle(f, s)
            pen = SVGPathPen(f.getGlyphSet())
            tp = TransformPen(pen, (s, 0, 0, -s, cur, y))
            for k, ct in enumerate(contours):
                if k == di:
                    continue
                for op, args in ct:
                    getattr(tp, op)(*args)
            ds.append(pen.getCommands())
            extras.append(f'<circle cx="{cur + dcx * s:.2f}" cy="{y - dcy * s + size * 0.045:.2f}" r="{dr * s * 1.08:.2f}" fill="{node_dot}"/>')
        else:
            ds.append(_glyph_d(f, g, cur, y, s))
        cur += hmtx[g][0] * s + track * size
    return ds, extras, cur - x - track * size


def text_svg(fontfile, text, size, x, y, fill, wght=None, track=0.0, node_dot=None):
    ds, extras, w = text_path(fontfile, text, size, x, y, wght, track, node_dot)
    return f'<path d="{" ".join(ds)}" fill="{fill}"/>' + "".join(extras), w


def cap_height(fontfile, size, wght=None):
    f = font(fontfile, wght)
    return f["OS/2"].sCapHeight * size / f["head"].unitsPerEm


PLEX_SB = "IBMPlexSans-SemiBold.ttf"
PLEX_MD = "IBMPlexSans-Medium.ttf"
PLEX_RG = "IBMPlexSans-Regular.ttf"
MONO = "JetBrainsMono[wght].ttf"
SERIF = "InstrumentSerif-Regular.ttf"


# ---------------------------------------------------------------- lockups
def wordmark(c, size=72, x=0, y=0):
    """'DevMind' outlined, 'i' dot replaced by the green evidence node."""
    return text_svg(PLEX_SB, "DevMind", size, x, y, c["text"], track=-0.012, node_dot=c["node"])


def lockup_h(c, bg=True, pad=24):
    """Horizontal lockup. Returns (svg, w, h)."""
    size = 84
    gap = 22
    ch = cap_height(PLEX_SB, size)
    baseline = 64 + ch / 2
    wm, w = wordmark(c, size, 128 + gap, baseline)
    W = 128 + gap + w
    inner = f'<g>{mark(c)}</g>{wm}'
    return wrap(inner, W, 128, c if bg else None, pad), W + 2 * pad, 128 + 2 * pad


def lockup_v(c, bg=True, pad=28):
    size = 64
    ch = cap_height(PLEX_SB, size)
    _, _, w = text_path(PLEX_SB, "DevMind", size, 0, 0, track=-0.012)
    W = max(w, 128)
    mk = f'<g transform="translate({(W - 128) / 2:.2f} 0)">{mark(c)}</g>'
    wm, _ = text_svg(PLEX_SB, "DevMind", size, (W - w) / 2, 128 + 30 + ch, c["text"], track=-0.012, node_dot=c["node"])
    H = 128 + 30 + ch
    return wrap(mk + wm, W, H, c if bg else None, pad), W + 2 * pad, H + 2 * pad


def wrap(inner, W, H, c, pad):
    w, h = W + 2 * pad, H + 2 * pad
    bg = f'<rect width="{w:.2f}" height="{h:.2f}" fill="{c["bg"]}"/>' if c and c.get("bg") else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="DevMind">{bg}<g transform="translate({pad} {pad})">{inner}</g></svg>')


def mark_svg(c, pad=0, bg=False):
    return wrap(mark(c), 128, 128, c if bg else None, pad)


def app_icon(c, rounded=True, scale=0.9):
    """Square app icon 128 grid. rounded=False -> full bleed (iOS / maskable)."""
    rx = 28 if rounded else 0
    t = (128 - 128 * scale) / 2
    border = (f'<rect x="1" y="1" width="126" height="126" rx="27" fill="none" stroke="#232B33" stroke-width="2"/>'
              if rounded and c["bg"] == DARK["bg"] else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128" role="img" '
            f'aria-label="DevMind"><rect width="128" height="128" rx="{rx}" fill="{c["bg"]}"/>{border}'
            f'<g transform="translate({t:.2f} {t:.2f}) scale({scale})">{mark(c)}</g></svg>')


def favicon_svg(c=DARK):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32" role="img" '
            f'aria-label="DevMind"><rect width="32" height="32" rx="7" fill="{c["bg"]}"/>{small_mark(c)}</svg>')


def animated_mark(c=DARK):
    css = """
<style>
.d{stroke-dasharray:260;stroke-dashoffset:0;animation:draw .7s cubic-bezier(.2,0,0,1) both}
.m{stroke-dasharray:140;stroke-dashoffset:0;animation:draw .6s .5s cubic-bezier(.2,0,0,1) both}
.n{animation:pop .24s calc(.5s + var(--i,0)*.1s) cubic-bezier(.2,0,0,1) both;transform-box:fill-box;transform-origin:center}
.core{animation:pop .24s 1.1s cubic-bezier(.2,0,0,1) both;transform-box:fill-box;transform-origin:center}
.ring{animation:fade .4s 1.2s both}
@keyframes draw{from{stroke-dashoffset:260}to{stroke-dashoffset:0}}
@keyframes pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:scale(1)}}
@keyframes fade{from{opacity:0}to{opacity:var(--op,.55)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
</style>"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128" role="img" '
            f'aria-label="DevMind">{css}{mark(c, anim=True)}</svg>')
