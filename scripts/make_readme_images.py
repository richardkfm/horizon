"""Regenerate the README's SVGs in docs/images/ (logo, animated ASCII morning, topic emblems).

A maintainer tool, not part of the app: it needs fontTools (`pip install fonttools`)
and an Inter Bold font file, whose outlines become the wordmark so the logo looks
the same everywhere. Run it after changing the emblems (web/emblems.py), the topic
inks (app.css), or the home page's ASCII scene (landing.html):

    python scripts/make_readme_images.py [path/to/Inter-Bold.otf]
"""

# ruff: noqa: E501 -- the SVG markup reads best as long literal lines.
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/images"
sys.path.insert(0, str(ROOT / "src"))
from horizon.web.emblems import TOPIC_EMBLEMS  # noqa: E402

THEMES = {
    "light": dict(
        bg="#f6f4ef",
        fg="#242120",
        muted="#5f5a53",
        line="#e0d9cc",
        acc="#2f6079",
        leaf="#456f3a",
        sun="#a8741f",
        glow="",
    ),
    "dark": dict(
        bg="#16181c",
        fg="#e9e5dc",
        muted="#a9a499",
        line="#2c3038",
        acc="#7fb0cb",
        leaf="#8fbf7f",
        sun="#e0b25c",
        glow="1",
    ),
}
INK = {}
css = (ROOT / "src/horizon/web/static/app.css").read_text()
for k, light, dark in re.findall(
    r'\[data-cat="(\w+)"\] \{ --cat-l: (#\w+); --cat-d: (#\w+); \}', css
):
    INK[k] = {"light": light, "dark": dark}
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

# --- logo: the header's brand mark + "horizon" outlined in Inter Bold --------
font = TTFont(
    sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
)
gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
upm = font["head"].unitsPerEm


def word_path(text, size, x0, baseline, tracking=0.0):
    scale = size / upm
    parts, x = [], x0
    for ch in text:
        g = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[g].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        parts.append(pen.getCommands())
        x += hmtx[g][0] * scale + tracking * size
    return " ".join(parts), x


MARK = """<defs>
    <clipPath id="c"><circle cx="16" cy="16" r="15.5"/></clipPath>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f3c98a"/><stop offset="1" stop-color="#fbe7c2"/></linearGradient>
    <linearGradient id="land" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8aa86f"/><stop offset="0.55" stop-color="#7fa07a"/><stop offset="1" stop-color="#7ba0bd"/></linearGradient>
  </defs>
  <g clip-path="url(#c)">
    <rect width="32" height="32" fill="url(#sky)"/>
    <circle cx="16" cy="17" r="6" fill="#fff6e3"/><circle cx="16" cy="17" r="4.2" fill="#fffaf0"/>
    <path d="M0,17 C6,15 10,16 16,19 C22,16 26,15 32,17 L32,32 L0,32 Z" fill="url(#land)"/>
  </g>
  <circle cx="16" cy="16" r="15" fill="none" stroke="{ring}" stroke-opacity="0.25" stroke-width="1"/>"""

for name, t in THEMES.items():
    d, end = word_path("horizon", 30, 44, 27, tracking=-0.005)
    w = int(end + 4)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 36" width="{w * 4}" height="144" role="img" aria-label="horizon">
  <title>horizon</title>
  <g transform="translate(0 2)">{MARK.format(ring=t["fg"])}</g>
  <path d="{d}" fill="{t["acc"]}"/>
</svg>
'''
    (OUT / f"logo-{name}.svg").write_text(svg)

# --- animated ASCII morning scene (from landing.html) ------------------------
tpl = (ROOT / "src/horizon/web/templates/landing.html").read_text()
ground = re.search(
    r'<pre class="hero-art-ground" aria-hidden="true">\n(.*?)</pre>', tpl, re.S
).group(1)
frames = re.findall(
    r"  <pre>(.*?)</pre>", tpl.split('<template id="hero-frames">')[1].split("</template>")[0], re.S
)
ground_lines = ground.split("\n")
COLS, CW, LH, FS, PAD = 60, 8.4, 17.5, 14, 28
H_ROWS = len(ground_lines)


def text_lines(lines, fill, extra=""):
    out = []
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        ln = ln.rstrip()
        y = PAD + 6 + (i + 1) * LH
        out.append(
            f'<text x="{PAD}" y="{y:.1f}" textLength="{len(ln) * CW:.1f}" lengthAdjust="spacing" '
            f'xml:space="preserve" fill="{fill}"{extra}>{html.escape(ln)}</text>'
        )
    return "\n    ".join(out)


W = int(PAD * 2 + COLS * CW)
H = int(PAD * 2 + 10 + H_ROWS * LH)
for name, t in THEMES.items():
    glow = ""
    if t["glow"]:
        glow = """<filter id="g" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>"""
    gattr = ' filter="url(#g)"' if t["glow"] else ""
    n = len(frames)
    frame_groups = []
    for i, fr in enumerate(frames):
        frame_groups.append(
            f'<g class="f f{i}"{gattr}>\n    {text_lines(fr.split(chr(10)), t["sun"])}\n  </g>'
        )
    # Each frame shows for 0.9 s in a loop (as on the home page); frame 0 is
    # the default so a viewer without animation still sees the whole scene.
    kf = []
    for i in range(n):
        a, b = 100 * i / n, 100 * (i + 1) / n
        kf.append(
            f"@keyframes k{i} {{ 0%, {a:.2f}% {{ opacity: 0 }} {a + 0.01:.2f}%, {b:.2f}% {{ opacity: 1 }} {b + 0.01:.2f}%, 100% {{ opacity: 0 }} }}"
        )
    rules = " ".join(f".f{i} {{ animation: k{i} {0.9 * n}s step-end infinite; }}" for i in range(n))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
     aria-label="An ASCII morning: the sun shines over a cottage with solar panels, a sunflower, a sapling and a small wind turbine, while birds cross the sky.">
  <title>horizon — an ASCII morning</title>
  <defs>{glow}</defs>
  <style>
    text {{ font-family: {MONO}; font-size: {FS}px; }}
    .f {{ opacity: 0; }} .f0 {{ opacity: 1; }}
    {" ".join(kf)}
    {rules}
    @media (prefers-reduced-motion: reduce) {{ .f {{ animation: none; }} }}
  </style>
  <rect width="100%" height="100%" rx="14" fill="{t["bg"]}"/>
  <g{gattr}>
    {text_lines(ground_lines, t["leaf"])}
  </g>
  {chr(10).join("  " + g for g in frame_groups)}
</svg>
'''
    (OUT / f"morning-{name}.svg").write_text(svg)

# --- the 15 topic emblems, drawn one after another --------------------------
COLW, ROWH, PERROW = 168, 116, 5
cats = list(TOPIC_EMBLEMS)
rows = (len(cats) + PERROW - 1) // PERROW
EW, EH = PAD * 2 + COLW * PERROW, PAD * 2 + ROWH * rows
for name, t in THEMES.items():
    cells = []
    for i, c in enumerate(cats):
        cx = PAD + (i % PERROW) * COLW + COLW / 2
        cy = PAD + (i // PERROW) * ROWH
        art = TOPIC_EMBLEMS[c].split("\n")
        width = max(len(row) for row in art)
        lines = []
        for j, ln in enumerate(art):
            x = cx - width * CW / 2
            if ln.strip():
                lines.append(
                    f'<text x="{x:.1f}" y="{cy + 22 + j * LH:.1f}" textLength="{len(ln) * CW:.1f}" lengthAdjust="spacing" xml:space="preserve" class="m">{html.escape(ln)}</text>'
                )
        cells.append(f'''<g class="e" style="animation-delay:{i * 0.12:.2f}s" fill="{INK[c][name]}">
    {"".join(lines)}
    <text x="{cx:.1f}" y="{cy + 22 + 3 * LH + 14:.1f}" text-anchor="middle" class="n">{c.capitalize()}</text>
  </g>''')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {EW} {EH}" width="{EW}" height="{EH}" role="img"
     aria-label="horizon's fifteen topics, each with its ASCII emblem: {", ".join(cats)}.">
  <title>horizon topics</title>
  <style>
    .m {{ font-family: {MONO}; font-size: {FS}px; }}
    .n {{ font-family: {SANS}; font-size: 13px; fill: {t["fg"]}; }}
    .e {{ opacity: 0; animation: in 0.5s ease-out forwards; }}
    @keyframes in {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
    @media (prefers-reduced-motion: reduce) {{ .e {{ animation: none; opacity: 1; }} }}
  </style>
  <rect width="100%" height="100%" rx="14" fill="{t["bg"]}"/>
  {chr(10).join("  " + c for c in cells)}
</svg>
'''
    (OUT / f"topics-{name}.svg").write_text(svg)
print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.svg"))))
