"""Gera os SVGs do README (tema claro e escuro).

As fontes são embutidas como subconjuntos WOFF2, porque um SVG carregado
via <img> no GitHub não consegue buscar fontes externas.

    pip install fonttools brotli pillow
    python scripts/build_assets.py

Caminhos das fontes podem ser trocados por variáveis de ambiente
(INTER_DIR, JETBRAINS_DIR). Ambas são OFL.
"""

import base64
import io
import os
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
MASCOT = OUT / "devzinh-mascot.png"

INTER_DIR = Path(os.environ.get("INTER_DIR", "/usr/share/fonts/opentype/inter"))
JB_DIR = Path(os.environ.get("JETBRAINS_DIR", "/usr/share/fonts/truetype/jetbrains-mono"))

FONTS = {
    "sans-500": (INTER_DIR / "Inter-Medium.otf", "Inter", 500),
    "sans-600": (INTER_DIR / "Inter-SemiBold.otf", "Inter", 600),
    "sans-800": (INTER_DIR / "Inter-ExtraBold.otf", "Inter", 800),
    "mono-400": (JB_DIR / "JetBrainsMono-Regular.ttf", "JB", 400),
    "mono-700": (JB_DIR / "JetBrainsMono-Bold.ttf", "JB", 700),
}
FALLBACK = {
    "Inter": "'Segoe UI',-apple-system,Helvetica,Arial,sans-serif",
    "JB": "ui-monospace,SFMono-Regular,Consolas,Menlo,monospace",
}

THEMES = {
    "dark": dict(
        panel="#0F141C", panel2="#151C27", border="#242D3B", grid="#1C2431",
        text="#E8EDF4", muted="#8D99AB", faint="#5A6577",
        orange="#FF8A1F", orange_soft="#FF8A1F", cyan="#2CD3EA", cream="#F7E3C8",
        glow_op="0.22", shadow="#000000", shadow_op="0.45",
    ),
    "light": dict(
        panel="#FFFBF5", panel2="#F6EFE4", border="#E8DDCC", grid="#EFE5D6",
        text="#1B2030", muted="#586172", faint="#9AA1AD",
        orange="#D2560A", orange_soft="#FF8A1F", cyan="#0B8394", cream="#B8742E",
        glow_op="0.16", shadow="#5A3A1A", shadow_op="0.18",
    ),
}

_metrics = {}


def font(key):
    if key not in _metrics:
        tt = TTFont(FONTS[key][0])
        _metrics[key] = (tt.getBestCmap(), tt["hmtx"].metrics, tt["head"].unitsPerEm)
    return _metrics[key]


def width(text, key, size):
    cmap, hmtx, upm = font(key)
    return sum(hmtx[cmap[ord(c)]][0] for c in text if ord(c) in cmap) * size / upm


class Svg:
    def __init__(self, w, h, theme, title):
        self.w, self.h, self.t, self.title = w, h, THEMES[theme], title
        self.parts, self.css, self.chars = [], [], {}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, key, size, fill, anchor="start", extra=""):
        self.chars.setdefault(key, set()).update(s)
        fam, wt = FONTS[key][1], FONTS[key][2]
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam},{FALLBACK[fam]}" '
            f'font-weight="{wt}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" {extra}>{escape(s)}</text>'
        )

    def _font_css(self):
        out = []
        for key, chars in self.chars.items():
            path, fam, wt = FONTS[key]
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "calt"]
            opts.name_IDs = []
            opts.notdef_outline = True
            tt = subset.load_font(str(path), opts)
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)) + " ")
            sub.subset(tt)
            buf = io.BytesIO()
            subset.save_font(tt, buf, opts)
            b64 = base64.b64encode(buf.getvalue()).decode()
            out.append(
                f"@font-face{{font-family:{fam};font-weight:{wt};"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
            )
        return "".join(out)

    def render(self):
        css = self._font_css() + "".join(self.css)
        css += "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
            f"<title>{escape(self.title)}</title><style>{css}</style>"
            + "".join(self.parts)
            + "</svg>"
        )


def mascot_uri(box=None, height=800):
    im = Image.open(MASCOT).convert("RGBA")
    if box:
        im = im.crop(box)
    w = round(im.width * height / im.height)
    im = im.resize((w, height), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=88, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def panel(s, rx=22):
    t = s.t
    s.add(
        f'<defs><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1.2" fill="{t["grid"]}"/></pattern>'
        f'<clipPath id="clip"><rect width="{s.w}" height="{s.h}" rx="{rx}"/></clipPath></defs>'
        f'<rect x="0.5" y="0.5" width="{s.w-1}" height="{s.h-1}" rx="{rx}" fill="{t["panel"]}" '
        f'stroke="{t["border"]}"/>'
        f'<rect width="{s.w}" height="{s.h}" rx="{rx}" fill="url(#dots)" opacity="0.9"/>'
    )


def pills(s, x, y, labels, color, key="mono-400", size=15, gap=10):
    for label in labels:
        w = width(label, key, size) + 26
        s.add(
            f'<rect x="{x}" y="{y-21}" width="{w:.1f}" height="32" rx="16" fill="none" '
            f'stroke="{color}" stroke-opacity="0.55"/>'
        )
        s.text(x + 13, y, label, key, size, color)
        x += w + gap
    return x


# ---------------------------------------------------------------- header

def header(theme):
    s = Svg(1200, 420, theme, "Rony Gabriel (Devzinh): Engenharia de Software, Python e C#/.NET")
    t = s.t
    panel(s)

    # brilho e trilhas de circuito atrás do mascote
    s.add(
        f'<defs><radialGradient id="glow"><stop offset="0" stop-color="{t["orange_soft"]}" '
        f'stop-opacity="{t["glow_op"]}"/><stop offset="1" stop-color="{t["orange_soft"]}" '
        f'stop-opacity="0"/></radialGradient></defs>'
        f'<g clip-path="url(#clip)"><circle cx="965" cy="215" r="260" fill="url(#glow)"/>'
    )
    traces = [
        "M1200 92 H1110 L1080 122 H1040",
        "M1200 300 H1140 L1110 270 H1070",
        "M790 360 H830 L860 330 H880",
        "M780 140 H812 L840 168 H866",
        "M1200 196 H1150",
    ]
    for i, d in enumerate(traces):
        s.add(f'<path d="{d}" fill="none" stroke="{t["cyan"]}" stroke-opacity="0.28" stroke-width="2"/>')
        s.add(
            f'<path class="sig" style="animation-delay:{i*0.9:.1f}s" d="{d}" fill="none" '
            f'stroke="{t["cyan"]}" stroke-width="2.5" stroke-linecap="round" pathLength="100" '
            f'stroke-dasharray="12 88"/>'
        )
    for cx, cy in [(1040, 122), (1070, 270), (880, 330), (866, 168), (1150, 196)]:
        s.add(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{t["panel"]}" stroke="{t["cyan"]}" stroke-width="2"/>')
    s.add("</g>")
    s.css.append(
        ".sig{stroke-dashoffset:100;animation:sig 4.5s linear infinite}"
        "@keyframes sig{0%{stroke-dashoffset:100;opacity:0}10%{opacity:1}"
        "60%{stroke-dashoffset:0;opacity:1}70%,100%{stroke-dashoffset:0;opacity:0}}"
    )

    # mascote
    s.add(
        f'<ellipse class="shadow" cx="960" cy="401" rx="92" ry="9" fill="{t["shadow"]}" '
        f'fill-opacity="{t["shadow_op"]}"/>'
        f'<g class="bob"><image href="{mascot_uri(height=780)}" x="830" y="14" width="260" height="390"/></g>'
    )
    s.css.append(
        ".bob{animation:bob 3.6s ease-in-out infinite}"
        "@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}"
        ".shadow{transform-origin:960px 401px;animation:sh 3.6s ease-in-out infinite}"
        "@keyframes sh{0%,100%{transform:scaleX(1)}50%{transform:scaleX(.9)}}"
    )

    x = 72
    s.text(x, 98, "~/devzinh", "mono-400", 18, t["cyan"])
    s.text(x + width("~/devzinh ", "mono-400", 18), 98, "❯ whoami", "mono-400", 18, t["muted"])
    s.text(x - 3, 178, "Rony Gabriel", "sans-800", 76, t["text"], extra='letter-spacing="-2"')
    s.text(x, 222, "Engenharia de Software · Python & C#/.NET", "sans-500", 24, t["muted"])

    tag = "Código para investigar, automatizar e simplificar."
    s.text(x, 292, "›", "mono-700", 22, t["orange"])
    tx = x + 24
    tw = width(tag, "mono-400", 22)
    n = len(tag)
    s.add(
        f'<defs><clipPath id="type"><rect class="typing" x="{tx}" y="266" width="{tw:.1f}" height="36"/>'
        f"</clipPath></defs><g clip-path=\"url(#type)\">"
    )
    s.text(tx, 292, tag, "mono-400", 22, t["text"])
    s.add("</g>")
    s.add(
        f'<g class="caret"><rect class="cursor" x="{tx+tw+4:.1f}" y="272" width="11" height="25" '
        f'fill="{t["orange"]}"/></g>'
    )
    s.css.append(
        f".typing{{transform-origin:{tx}px 0;animation:type 2.6s steps({n}) .4s both}}"
        "@keyframes type{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        f".caret{{animation:caret 2.6s steps({n}) .4s both}}"
        f"@keyframes caret{{from{{transform:translateX(-{tw:.1f}px)}}to{{transform:none}}}}"
        ".cursor{animation:blink 1s step-end infinite}"
        "@keyframes blink{50%{opacity:0}}"
    )

    pills(s, x, 360, ["backend", "automação", "segurança", "ferramentas de terminal"], t["cyan"])
    return s


# ------------------------------------------------------------ project cards

def card_text(s, x, y, num, name, question, lines, tags, name_size=40, inline_link=False):
    t = s.t
    s.text(x, y, num, "mono-700", 16, t["orange"], extra='letter-spacing="2"')
    s.text(x, y + 50, name, "sans-800", name_size, t["text"], extra='letter-spacing="-1"')
    s.text(x, y + 88, question, "sans-600", 20, t["orange"])
    for i, line in enumerate(lines):
        s.text(x, y + 126 + i * 26, line, "sans-500", 17, t["muted"])
    yy = y + 126 + len(lines) * 26 + 34
    pills(s, x, yy, tags, t["muted"], size=14, gap=8)
    ly = yy if inline_link else s.h - 34
    s.text(s.w - 40, ly, "ver repositório →", "mono-400", 15, t["cyan"], anchor="end")


def ghosttrace(theme):
    s = Svg(1200, 360, theme, "GhostTrace: análise forense local de rastros de software no Windows")
    t = s.t
    panel(s)
    card_text(
        s, 52, 70, "01", "GhostTrace",
        "O que um software deixa para trás no Windows?",
        ["Análise forense local: reúne rastros de execução,",
         "persistência e arquivos residuais para a investigação."],
        ["C#", ".NET", "Windows", "forense"],
    )

    # console ilustrativo das áreas inspecionadas
    px, py, pw, ph = 660, 40, 500, 230
    s.add(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="14" fill="{t["panel2"]}" stroke="{t["border"]}"/>')
    s.text(px + 22, py + 34, "ghosttrace scan", "mono-700", 14, t["text"])
    s.text(px + pw - 22, py + 34, "local · somente leitura", "mono-400", 13, t["faint"], anchor="end")
    s.add(f'<line x1="{px}" y1="{py+50}" x2="{px+pw}" y2="{py+50}" stroke="{t["border"]}"/>')
    rows = [
        ("registro", r"HKCU\...\CurrentVersion\Run"),
        ("serviços", r"HKLM\SYSTEM\...\Services"),
        ("tarefas", r"Task Scheduler\Library"),
        ("arquivos", r"%APPDATA%  %PROGRAMDATA%"),
        ("execução", "rastros de execução"),
    ]
    for i, (k, v) in enumerate(rows):
        yy = py + 84 + i * 32
        d = 0.5 + i * 0.45
        s.add(f'<g class="row" style="animation-delay:{d:.2f}s">')
        s.text(px + 22, yy, "●", "mono-400", 12, t["cyan"])
        s.text(px + 44, yy, k, "mono-700", 14, t["orange"])
        s.text(px + 150, yy, v, "mono-400", 14, t["muted"])
        s.add("</g>")
    s.add(
        f'<rect class="scan" x="{px+1}" y="{py+62}" width="{pw-2}" height="30" '
        f'fill="{t["cyan"]}" fill-opacity="0.08"/>'
    )
    s.css.append(
        ".row{animation:row .35s ease-out both}"
        "@keyframes row{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}"
        ".scan{animation:scan 5s ease-in-out .5s infinite}"
        "@keyframes scan{0%{transform:translateY(0);opacity:0}8%{opacity:1}"
        "60%{transform:translateY(128px);opacity:1}70%,100%{transform:translateY(128px);opacity:0}}"
    )
    return s


def sessionbridge(theme):
    s = Svg(588, 430, theme, "SessionBridge: servidor MCP com sessão de navegador persistente")
    t = s.t
    panel(s)

    # cliente IA -> você (login) -> navegador
    y = 100
    s.add(f'<circle class="pkt" cx="92" cy="{y}" r="6" fill="{t["cyan"]}"/>')
    nodes = [(92, "cliente IA"), (294, "você"), (496, "navegador")]
    s.add(f'<line x1="92" y1="{y}" x2="496" y2="{y}" stroke="{t["border"]}" stroke-width="2" stroke-dasharray="4 6"/>')
    for i, (cx, label) in enumerate(nodes):
        stroke = t["orange"] if i == 1 else t["cyan"]
        cls = ' class="wait"' if i == 1 else ""
        s.add(f'<circle{cls} cx="{cx}" cy="{y}" r="22" fill="{t["panel2"]}" stroke="{stroke}" stroke-width="2"/>')
        s.text(cx, y + 50, label, "mono-400", 13, t["muted"], anchor="middle")
    s.text(92, y + 5, "MCP", "mono-700", 11, t["cyan"], anchor="middle")
    s.text(294, y + 5, "login", "mono-700", 11, t["orange"], anchor="middle")
    s.text(496, y + 5, "CDP", "mono-700", 11, t["cyan"], anchor="middle")
    s.css.append(
        ".wait{animation:wait 5s ease-in-out infinite}"
        "@keyframes wait{0%,28%,58%,100%{stroke-width:2}36%,50%{stroke-width:5}}"
    )
    s.css.append(
        ".pkt{animation:pkt 5s ease-in-out infinite}"
        "@keyframes pkt{0%{transform:translateX(0);opacity:0}6%{opacity:1}"
        "30%,55%{transform:translateX(202px);fill:" + t["orange"] + "}"
        "85%{transform:translateX(404px);opacity:1;fill:" + t["cyan"] + "}"
        "95%,100%{transform:translateX(404px);opacity:0}}"
    )
    card_text(
        s, 40, 190, "02", "SessionBridge",
        "Uma automação precisa de você. E depois?",
        ["Mantém o navegador aberto e a sessão viva enquanto",
         "você faz o login; a IA continua no mesmo contexto."],
        ["Python", "MCP", "Playwright", "CDP"], name_size=34, inline_link=True,
    )
    return s


def pert(theme):
    s = Svg(588, 430, theme, "PERT Calculator: estimativa de prazos com três cenários no terminal")
    t = s.t
    panel(s)

    # curva beta-PERT para O=2, M=5, P=12 (te = 5.67)
    import math
    o, m, p = 2.0, 5.0, 12.0
    a = 1 + 4 * (m - o) / (p - o)
    b = 1 + 4 * (p - m) / (p - o)
    x0, x1, base, hmax = 60, 528, 132, 74
    xs = [i / 200 for i in range(201)]
    ys = [(u ** (a - 1)) * ((1 - u) ** (b - 1)) for u in xs]
    peak = max(ys)
    pts = [(x0 + u * (x1 - x0), base - v / peak * hmax) for u, v in zip(xs, ys)]
    d = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    s.add(f'<path d="{d} L{x1} {base} L{x0} {base}Z" fill="{t["cyan"]}" fill-opacity="0.08"/>')
    s.add(f'<line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" stroke="{t["border"]}" stroke-width="2"/>')
    s.add(
        f'<path class="curve" d="{d}" fill="none" stroke="{t["cyan"]}" stroke-width="3" '
        f'stroke-linecap="round" pathLength="100" stroke-dasharray="100"/>'
    )
    s.css.append(
        ".curve{animation:draw 1.8s ease-out .3s both}"
        "@keyframes draw{from{stroke-dashoffset:100}to{stroke-dashoffset:0}}"
        ".te{animation:fade .5s ease-out 1.8s both}@keyframes fade{from{opacity:0}to{opacity:1}}"
    )
    def X(v):
        return x0 + (v - o) / (p - o) * (x1 - x0)
    for v, lab in [(o, "O"), (m, "M"), (p, "P")]:
        s.add(f'<line x1="{X(v):.1f}" y1="{base}" x2="{X(v):.1f}" y2="{base+6}" stroke="{t["muted"]}" stroke-width="2"/>')
        s.text(X(v), base + 24, lab, "mono-700", 13, t["muted"], anchor="middle")
    te = (o + 4 * m + p) / 6
    s.add(
        f'<g class="te"><line x1="{X(te):.1f}" y1="{base}" x2="{X(te):.1f}" y2="{base-hmax-18}" '
        f'stroke="{t["orange"]}" stroke-width="2" stroke-dasharray="4 4"/>'
    )
    s.text(X(te) + 10, base - hmax - 12, "tₑ = (O + 4M + P) / 6", "mono-400", 13, t["orange"])
    s.add("</g>")

    card_text(
        s, 40, 190, "03", "PERT Calculator",
        "Como estimar um prazo com incerteza?",
        ["Combina cenários otimista, provável e pessimista",
         "e gera prazo esperado, desvio padrão e variância."],
        ["Python", "CLI", "PERT"], name_size=34, inline_link=True,
    )
    return s


# ---------------------------------------------------------------- footer

def footer(theme):
    s = Svg(1200, 200, theme, "Obrigado pela visita")
    t = s.t
    panel(s)
    s.add('<g clip-path="url(#clip)">')
    # recorte da cabeça: a raposa espia pela borda inferior
    s.add(f'<g class="peek"><image href="{mascot_uri(box=(150, 0, 870, 640), height=440)}" '
          f'x="850" y="34" width="248" height="220"/></g>')
    s.add("</g>")
    s.css.append(
        ".peek{animation:peek 1.1s cubic-bezier(.2,.9,.3,1.2) .2s both}"
        "@keyframes peek{from{transform:translateY(170px)}to{transform:none}}"
    )
    s.text(72, 86, "❯ exit 0", "mono-700", 20, t["cyan"])
    s.text(72, 132, "Obrigado pela visita.", "sans-800", 36, t["text"], extra='letter-spacing="-1"')
    s.text(72, 164, "Rony Gabriel · Devzinh", "sans-500", 18, t["muted"])
    return s


def main():
    builds = {"header": header, "card-ghosttrace": ghosttrace,
              "card-sessionbridge": sessionbridge, "card-pert": pert, "footer": footer}
    for name, fn in builds.items():
        for theme in THEMES:
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(fn(theme).render(), encoding="utf-8")
            print(f"{path.relative_to(ROOT)}  {path.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
