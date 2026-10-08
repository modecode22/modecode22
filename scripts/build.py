"""Draws the profile README's images in moncef.net's design.

    python scripts/build.py [path/to/moncef/public/fonts]

GitHub strips CSS from a README, so the site's look lives in SVGs: the paper
grid with its registration crosses, the Alexandria headline with the orange
caret, the numbered section heads. Each comes light and dark (the README picks
with <picture>). The faces are subset to the letters each image uses and
embedded, so the images render the same everywhere without loading a font.

Colours are the site's tokens (packages/ui tokens.css), converted from OKLCH.
"""
import base64, io, math, os, sys
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/Desktop/personal/main-projects/selance-v6/apps/moncef/public/fonts"
)
OUT = os.path.join(ROOT, "assets")
W = 1200


# ---- colour: OKLCH -> sRGB hex ------------------------------------------------
def oklch(l, c, h):
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_, m_, s_ = l + 0.3963377774 * a + 0.2158037573 * b, l - 0.1055613458 * a - 0.0638541728 * b, l - 0.0894841775 * a - 1.2914855480 * b
    l3, m3, s3 = l_**3, m_**3, s_**3
    rgb = (
        4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3,
        -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3,
        -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3,
    )
    def enc(x):
        x = min(1, max(0, x))
        return round(255 * (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055))
    return "#%02x%02x%02x" % tuple(enc(x) for x in rgb)


N = {k: oklch(*v) for k, v in {
    50: (0.985, 0.002, 264), 100: (0.967, 0.003, 264), 200: (0.925, 0.005, 264), 300: (0.87, 0.007, 264),
    400: (0.71, 0.01, 264), 500: (0.552, 0.012, 264), 600: (0.446, 0.012, 264), 700: (0.373, 0.012, 264),
    800: (0.278, 0.011, 264), 900: (0.21, 0.01, 264), 950: (0.165, 0.009, 264),
}.items()}
ORANGE = oklch(0.66, 0.22, 38)

THEMES = {
    "light": dict(ground=N[50], ink=N[950], text=N[600], mute=N[500], rule=N[200], grid=N[200], cross=N[300]),
    "dark": dict(ground=N[950], ink=N[50], text=N[400], mute=N[500], rule=N[800], grid=N[900], cross=N[700]),
}


# ---- faces --------------------------------------------------------------------
FACES = {
    "display": ("Alexandria", 700, "alexandria-latin-700.woff2"),
    "sans": ("IBM Plex Sans", 400, "plex-arabic-latin-400.woff2"),
    "sans-bold": ("IBM Plex Sans", 600, "plex-arabic-latin-600.woff2"),
    "mono": ("IBM Plex Mono", 500, "plex-mono-latin-500.woff2"),
}
_fonts = {k: TTFont(os.path.join(FONTS, f)) for k, (_, _, f) in FACES.items()}


def measure(face, text, size):
    font = _fonts[face]
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    units = sum(hmtx[cmap.get(ord(ch), cmap[ord("?")])][0] for ch in text)
    return units * size / font["head"].unitsPerEm


def embed(used):
    """@font-face rules for the faces an image uses, subset to its letters."""
    rules = []
    for face, chars in used.items():
        family, weight, file = FACES[face]
        font = TTFont(os.path.join(FONTS, file))
        options = Options()
        options.flavor = "woff2"
        options.layout_features = ["kern", "liga"]
        sub = Subsetter(options)
        sub.populate(text="".join(sorted(set(chars))) + " ")
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        data = base64.b64encode(buf.getvalue()).decode()
        rules.append(
            f"@font-face{{font-family:'{family} Sub';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
        )
    return "".join(rules)


def fam(face):
    family, weight, _ = FACES[face]
    fallback = "ui-monospace,monospace" if face == "mono" else "system-ui,sans-serif"
    return f"font-family:'{family} Sub',{fallback};font-weight:{weight}"


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cross(x, y, color, r=6):
    return f'<path d="M{x - r} {y}h{2 * r}M{x} {y - r}v{2 * r}" stroke="{color}" stroke-width="1.2"/>'


def grid(t, height, step=34, every=4):
    """The site's ground: a faint square grid, a cross at every fourth line, fading out."""
    lines = "".join(f'<path d="M{x} 0V{height}"/>' for x in range(0, W + 1, step))
    lines += "".join(f'<path d="M0 {y}H{W}"/>' for y in range(0, height + 1, step))
    crosses = "".join(
        cross(x, y, t["cross"]) for x in range(step * every, W, step * every) for y in range(step * every // 2 * 2, height, step * every)
    )
    return (
        '<defs><radialGradient id="fade" cx="78%" cy="20%" r="85%">'
        '<stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        f'</radialGradient><mask id="m"><rect width="{W}" height="{height}" fill="url(#fade)"/></mask></defs>'
        f'<g mask="url(#m)"><g stroke="{t["grid"]}" stroke-width="1" opacity=".7">{lines}</g>{crosses}</g>'
    )


def wrap(face, text, size, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if measure(face, trial, size) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


# ---- the header -------------------------------------------------------------
HEADLINE = ["I'm Moncef.", "I build products", "for the web."]
EYEBROW = "FULL-STACK DEVELOPER · EL OUED, ALGERIA"
LEDE = ("I lead Selance, a studio that builds websites, online stores and apps for businesses in "
        "Saudi Arabia, Qatar and Algeria, and I make products of my own on the side.")


def header(theme):
    t = THEMES[theme]
    pad, top = 64, 150
    size, lead = 84, 96
    lede_size, lede_lead = 25, 40
    lede = wrap("sans", LEDE, lede_size, 820)
    height = top + 40 + lead * len(HEADLINE) + 34 + lede_lead * len(lede) + 64
    used = {"display": "moncef" + "".join(HEADLINE), "mono": EYEBROW + "moncef.net", "sans": LEDE, "sans-bold": "Selance"}

    # A panel (the site's 21px radius) with a hairline, so it sits on GitHub's own page.
    parts = [
        f'<clipPath id="panel"><rect width="{W}" height="{height}" rx="21"/></clipPath><g clip-path="url(#panel)">',
        f'<rect width="{W}" height="{height}" fill="{t["ground"]}"/>',
        grid(t, height),
    ]
    # The wordmark, its caret, and the address on the other side.
    parts.append(f'<text x="{pad}" y="70" style="{fam("display")}" font-size="30" fill="{t["ink"]}">moncef</text>')
    parts.append(f'<rect x="{pad + measure("display", "moncef", 30) + 3}" y="45" width="3.5" height="32" fill="{ORANGE}"/>')
    parts.append(f'<text x="{W - pad}" y="68" text-anchor="end" style="{fam("mono")}" font-size="17" fill="{t["mute"]}">moncef.net</text>')
    # The eyebrow, with the site's pin.
    parts.append(
        f'<g transform="translate({pad} {top - 18}) scale(1.1)" fill="none" stroke="{t["mute"]}" stroke-width="1.6">'
        '<path d="M8 1.5a5.5 5.5 0 0 1 5.5 5.5c0 4-5.5 9.5-5.5 9.5S2.5 11 2.5 7A5.5 5.5 0 0 1 8 1.5z"/><circle cx="8" cy="7" r="1.8"/></g>'
    )
    parts.append(
        f'<text x="{pad + 28}" y="{top}" style="{fam("mono")}" font-size="18" letter-spacing="1.6" fill="{t["mute"]}">{esc(EYEBROW)}</text>'
    )
    # The headline, and the caret that blinks after it.
    y = top + 40
    for line in HEADLINE:
        y += lead
        parts.append(f'<text x="{pad - 3}" y="{y}" style="{fam("display")}" font-size="{size}" fill="{t["ink"]}">{esc(line)}</text>')
    caret_x = pad + measure("display", HEADLINE[-1], size) + 8
    parts.append(f'<rect class="caret" x="{caret_x:.1f}" y="{y - size * 0.86:.1f}" width="5" height="{size * 1.02:.1f}" fill="{ORANGE}"/>')
    # The lede, «Selance» set like the site's link: ink, underlined in orange.
    y += 34
    for line in lede:
        y += lede_lead
        if "Selance" in line:
            before, after = line.split("Selance", 1)
            x0 = pad + measure("sans", before, lede_size)
            wsel = measure("sans-bold", "Selance", lede_size)
            parts.append(
                f'<text x="{pad}" y="{y}" style="{fam("sans")}" font-size="{lede_size}" fill="{t["text"]}">{esc(before)}'
                f'<tspan style="{fam("sans-bold")}" fill="{t["ink"]}">Selance</tspan>{esc(after)}</text>'
            )
            parts.append(f'<rect x="{x0:.1f}" y="{y + 7}" width="{wsel:.1f}" height="2.5" fill="{ORANGE}"/>')
        else:
            parts.append(f'<text x="{pad}" y="{y}" style="{fam("sans")}" font-size="{lede_size}" fill="{t["text"]}">{esc(line)}</text>')

    parts.append("</g>")
    parts.append(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{height - 1.5}" rx="20.5" fill="none" stroke="{t["rule"]}" stroke-width="1.5"/>')
    style = embed(used) + (
        ".caret{animation:blink 1.1s steps(1) infinite}"
        "@keyframes blink{50%{opacity:0}}"
        "@media (prefers-reduced-motion:reduce){.caret{animation:none}}"
    )
    return svg(height, style, parts, "Moncef Aissaoui. I'm Moncef. I build products for the web.")


# ---- a section head -----------------------------------------------------------
def section(theme, number, title):
    t = THEMES[theme]
    pad, height = 4, 96
    used = {"display": title, "mono": number}
    nx = pad
    tx = nx + measure("mono", number, 18) + 16
    parts = [
        f'<text x="{nx}" y="58" style="{fam("mono")}" font-size="18" fill="{ORANGE}">{number}</text>',
        f'<text x="{tx}" y="60" style="{fam("display")}" font-size="40" fill="{t["ink"]}">{esc(title)}</text>',
        f'<path d="M{pad} 84H{W - pad}" stroke="{t["rule"]}" stroke-width="1.5"/>',
        cross(pad + 6, 84, t["cross"], 7),
        cross(W - pad - 6, 84, t["cross"], 7),
    ]
    return svg(height, embed(used), parts, f"{number} {title}")


def svg(height, style, parts, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" role="img" aria-label="{esc(label)}">'
        f"<style>{style}</style>{''.join(parts)}</svg>\n"
    )


SECTIONS = [
    ("01", "Building now"),
    ("02", "Built for clients"),
    ("03", "Range"),
    ("04", "How I build"),
    ("05", "Let's talk."),
]

os.makedirs(OUT, exist_ok=True)
for theme in THEMES:
    with open(os.path.join(OUT, f"header-{theme}.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(header(theme))
    for number, title in SECTIONS:
        slug = title.lower().replace("'", "").replace(".", "").replace(" ", "-")
        with open(os.path.join(OUT, f"{number}-{slug}-{theme}.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(section(theme, number, title))
print("written", sorted(os.listdir(OUT)))
