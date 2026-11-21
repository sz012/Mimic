import json
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "logo"

INK = "#0E0E11"
WHITE = "#F4F4F1"
ACCENT = "#5546FF"
ACCENT_DARK = "#8D84FF"

XH = 100
W = XH * 7.2 / 26
R = XH * 9.6 / 26
DX, DY = -XH * 5.2 / 26, -XH * 5.2 / 26
KNOCK = XH * 4.4 / 26
GAP = 11
GAP_AFTER_M = GAP
C_R = 52
C_DEG = 44


def f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def n_shape(x0, top, base):
    cy = top + R
    return (
        f"M{f(x0)} {f(base)}V{f(cy)}A{f(R)} {f(R)} 0 0 1 {f(x0 + 2 * R)} {f(cy)}"
        f"V{f(base)}H{f(x0 + 2 * R - W)}V{f(cy)}A{f(R - W)} {f(R - W)} 0 0 0 {f(x0 + W)} {f(cy)}"
        f"V{f(base)}Z"
    )


def m_shape(x0, top=0, base=XH):
    return n_shape(x0, top, base) + n_shape(x0 + 2 * R - W, top, base)


def m_hull(x0, top=0, base=XH):
    cy = top + R
    x1 = x0 + 2 * R - W
    return (
        f"M{f(x0)} {f(base)}V{f(cy)}A{f(R)} {f(R)} 0 0 1 {f(x0 + 2 * R)} {f(cy)}"
        f"L{f(x1)} {f(cy)}A{f(R)} {f(R)} 0 0 1 {f(x1 + 2 * R)} {f(cy)}V{f(base)}Z"
    )


def stem(x):
    return f"M{f(x)} 0H{f(x + W)}V{XH}H{f(x)}Z"


def c_shape(cx, cy):
    t = math.radians(C_DEG)
    r = C_R - W - 0.8
    ox, oy = C_R * math.cos(t), C_R * math.sin(t)
    ix, iy = r * math.cos(t), r * math.sin(t)
    return (
        f"M{f(cx + ox)} {f(cy - oy)}A{C_R} {C_R} 0 1 0 {f(cx + ox)} {f(cy + oy)}"
        f"L{f(cx + ix)} {f(cy + iy)}A{f(r)} {f(r)} 0 1 1 {f(cx + ix)} {f(cy - iy)}Z"
    )


M_W = 4 * R - W


def geometry():
    x = M_W + GAP_AFTER_M
    i1 = x
    x += W + GAP
    m2 = x
    x += M_W + GAP
    i2 = x
    x += W + GAP - 3
    cx = x + C_R
    letters = {"i1": stem(i1), "m": m_shape(m2), "i2": stem(i2), "c": c_shape(cx, 50)}
    return {
        "front": m_shape(0), "back": m_shape(DX, DY, XH + DY), "hull": m_hull(0),
        "knock": KNOCK, "offset": [DX, DY], "letters": letters, "imic": "".join(letters.values()),
        "right": cx + C_R * math.cos(math.radians(C_DEG)), "left": DX, "m_width": M_W, "xh": XH,
    }


def mask(uid, hull, x, y, w, h):
    return (
        f'<defs><mask id="k{uid}" maskUnits="userSpaceOnUse" x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}">'
        f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="#fff"/>'
        f'<path d="{hull}" fill="#000" stroke="#000" stroke-width="{f(KNOCK)}" stroke-linejoin="round"/></mask></defs>'
    )


def lockup_svg(g, main, accent, uid):
    top = DY - 3
    vb = f"{f(DX - 3)} {f(top)} {f(g['right'] - DX + 6)} {f(XH + 3 - top)}"
    body = mask(uid, g["hull"], -50, -100, 1000, 300)
    body += f'<path d="{g["back"]}" fill="{accent}" mask="url(#k{uid})"/>'
    body += f'<path fill="{main}" d="{g["front"]}{g["imic"]}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">{body}</svg>\n'


def mark_body(g, main, accent, uid, box=36):
    w, h = M_W - DX, XH - DY
    s = box / max(w, h)
    tx = 24 - w * s / 2 - DX * s
    ty = 24 - h * s / 2 - DY * s
    inner = mask(uid, g["hull"], -50, -100, 300, 300)
    inner += f'<path d="{g["back"]}" fill="{accent}" mask="url(#k{uid})"/><path d="{g["front"]}" fill="{main}"/>'
    return f'<g transform="translate({f(tx)} {f(ty)}) scale({f(s)})">{inner}</g>'


def mark_svg(g, main, accent, uid):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">{mark_body(g, main, accent, uid)}</svg>\n'


def favicon_svg(g):
    body = f'<rect width="48" height="48" rx="11" fill="{INK}"/>' + mark_body(g, WHITE, ACCENT_DARK, "f", box=32)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">{body}</svg>\n'


def build(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.svg"):
        old.unlink()
    g = geometry()
    files = {
        "logo.svg": lockup_svg(g, INK, ACCENT, "1"),
        "logo-dark.svg": lockup_svg(g, WHITE, ACCENT_DARK, "2"),
        "logo-mono.svg": lockup_svg(g, INK, INK, "3"),
        "logo-mono-white.svg": lockup_svg(g, "#FFFFFF", "#FFFFFF", "4"),
        "logo-mark.svg": mark_svg(g, INK, ACCENT, "6"),
        "logo-mark-dark.svg": mark_svg(g, WHITE, ACCENT_DARK, "7"),
        "logo-mark-mono.svg": mark_svg(g, INK, INK, "8"),
        "logo-mark-mono-white.svg": mark_svg(g, "#FFFFFF", "#FFFFFF", "9"),
        "favicon.svg": favicon_svg(g),
    }
    for name, content in files.items():
        (out / name).write_text(content)
    (out / "logo-geometry.json").write_text(json.dumps(g))


if __name__ == "__main__":
    if len(sys.argv) > 2:
        GAP, GAP_AFTER_M = float(sys.argv[1]), float(sys.argv[2])
        build(Path(sys.argv[3]))
    else:
        build()
