"""Make the app's font subsets (assets/fonts) from the full fonts, keeping every character they had and adding what
tools/check_fonts.py found missing.

    python3 tools/make_fonts.py [SOURCES]    # SOURCES/gfonts = google/fonts (ofl/atkinsonhyperlegible, ofl/gentiumplus)

The full fonts come from github.com/google/fonts (OFL), fetched by tools/fetch_sources.sh. Noto Serif Hebrew is left
as it is (check_fonts finds nothing missing). Added 19 Nov 2026:
  Atkinson: Latin Extended-A that Atkinson Hyperlegible has (ē Ē ā … for transliterations), and ō Ō, which it lacks:
            made here as composites of o/O and its own macron, placed like its ē and ô (OFL: Atkinson Hyperlegible has
            no Reserved Font Name, so a modified version may keep the name; the licence stays with it)
  Gentium:  Latin Extended-A, modifier letters (ˈ), SBL's double brackets ⟦ ⟧, arrows and ✓ ✗ used on screens
"""
import os, sys
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SOURCES", "/home/claude/src")
G = os.path.join(SRC, "gfonts", "ofl")
LATIN_EXT_A = set(range(0x0100, 0x0180))
EXTRA = {
    "atkinson": LATIN_EXT_A,
    "gentium": LATIN_EXT_A | set(range(0x02B0, 0x0300)) | {0x27E6, 0x27E7, 0x2190, 0x2191, 0x2192, 0x2193, 0x2197,
                                                             0x21BB, 0x2913, 0x25B6, 0x2264, 0x2265, 0x2713, 0x2717},
}
FONTS = [  # (output, source, family)
    ("atkinson-regular.woff", "atkinsonhyperlegible/AtkinsonHyperlegible-Regular.ttf", "atkinson"),
    ("atkinson-bold.woff", "atkinsonhyperlegible/AtkinsonHyperlegible-Bold.ttf", "atkinson"),
    ("gentium-plus-regular.woff", "gentiumplus/GentiumPlus-Regular.ttf", "gentium"),
    ("gentium-plus-bold.woff", "gentiumplus/GentiumPlus-Bold.ttf", "gentium"),
    ("gentium-plus-italic.woff", "gentiumplus/GentiumPlus-Italic.ttf", "gentium"),
]


def add_composite(font, name, unicode_, base, with_macron, like_base, like):
    """Add glyph `name` = base + the macron of `with_macron` (ē for ō), the macron moved by as much as the circumflex
    of `like` (ô) sits further along than that of `like_base` (ê): ō's macron then sits over o as ē's sits over e."""
    glyf, hmtx = font["glyf"], font["hmtx"]
    if name in glyf.glyphs:
        return False
    cmap = font.getBestCmap()
    dx = glyf[cmap[like]].components[1].x - glyf[cmap[like_base]].components[1].x
    dy = glyf[cmap[like]].components[1].y - glyf[cmap[like_base]].components[1].y
    m = glyf[cmap[with_macron]].components[1]
    g = Glyph()
    g.numberOfContours = -1
    a = GlyphComponent(); a.glyphName = base; a.x = 0; a.y = 0; a.flags = 0x0204  # ROUND_XY_TO_GRID | USE_MY_METRICS
    b = GlyphComponent(); b.glyphName = m.glyphName; b.x = m.x + dx; b.y = m.y + dy; b.flags = 0x0004
    g.components = [a, b]
    glyf.glyphs[name] = g
    order = font.getGlyphOrder() + [name]
    font.setGlyphOrder(order)
    glyf.glyphOrder = order
    hmtx.metrics[name] = hmtx.metrics[base]
    for t in font["cmap"].tables:
        if t.isUnicode():
            t.cmap[unicode_] = name
    g.recalcBounds(glyf)
    return True


def main():
    for out, src, fam in FONTS:
        path = os.path.join(G, src)
        if not os.path.exists(path):
            sys.exit(f"Missing {path}: run tools/fetch_sources.sh {SRC}")
        current = set(TTFont(os.path.join(ROOT, "assets", "fonts", out)).getBestCmap())
        full = TTFont(path)
        have = set(full.getBestCmap())
        keep = sorted((current | EXTRA[fam]) & have)
        opts = subset.Options()
        opts.layout_features = ["*"]
        opts.notdef_outline = True
        opts.flavor = "woff"
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=keep)
        sub.subset(full)
        added = []
        if fam == "atkinson":
            # o + its macron, placed like ô is placed over o compared with ê over e
            if add_composite(full, "omacron", 0x014D, "o", 0x0113, 0x00EA, 0x00F4):
                added.append("ō")
            if add_composite(full, "Omacron", 0x014C, "O", 0x0112, 0x00CA, 0x00D4):
                added.append("Ō")
        full.flavor = "woff"
        full.save(os.path.join(ROOT, "assets", "fonts", out))
        now = set(TTFont(os.path.join(ROOT, "assets", "fonts", out)).getBestCmap())
        print(f"{out}: {len(current)} → {len(now)} characters (+{len(now - current)}{', made ' + ' '.join(added) if added else ''}), "
              f"{os.path.getsize(os.path.join(ROOT, 'assets', 'fonts', out)) // 1024} KB")


if __name__ == "__main__":
    main()
