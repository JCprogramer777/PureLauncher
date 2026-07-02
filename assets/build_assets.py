"""Genera la marca de PureLauncher a partir de una unica geometria:
- ui/logo.svg  (interfaz, vectorial)
- assets/logo.png (1024px)
- assets/icon.ico (icono de la app / instalador)

Diseno: cubo isometrico facetado verde/turquesa con flecha ascendente,
recreacion vectorial del logo original del proyecto.
"""

import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ------------------------------------------------------------------ geometria

S3 = math.sqrt(3) / 2
R = 100.0
T = (0, -R)
TR = (S3 * R, -R / 2)
BR = (S3 * R, R / 2)
B = (0, R)
BL = (-S3 * R, R / 2)
TL = (-S3 * R, -R / 2)
C = (0.0, 0.0)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def left_face(u, v):
    """Parametriza la cara izquierda (TL, C, B, BL)."""
    return (-S3 * R + S3 * R * u, -R / 2 + (R / 2) * u + R * v)


def right_face(u, v):
    """Parametriza la cara derecha (C, TR, BR, B)."""
    return (S3 * R * u, -(R / 2) * u + R * v)


def scale_about(points, center, k):
    return [lerp(center, p, k) for p in points]


# Facetas ------------------------------------------------------------------
TOP_CENTROID = (0, -R / 2)
top_left_tri = [T, C, TL]
top_right_tri = [T, TR, C]
inset = scale_about([T, TR, C, TL], TOP_CENTROID, 0.52)
inset_left = [inset[0], inset[2], inset[3]]
inset_right = [inset[0], inset[1], inset[2]]

left_up_tri = [TL, C, B]
left_low_tri = [TL, B, BL]
right_up_tri = [C, TR, BR]
right_low_tri = [C, BR, B]

COLORS = {
    "top_l": "#2fb576",
    "top_r": "#5fdda2",
    "inset_l": "#2ab8d4",
    "inset_r": "#8fe9f5",
    "left_u": "#23a765",
    "left_d": "#1b8f55",
    "right_u": "#3ec6e0",
    "right_d": "#1ba6c8",
    "edge": "#ffffff",
    "arrow": "#2ecc71",
}

# Laberinto (marca "P") en la cara izquierda -------------------------------
maze_uv = [(0.20, 0.20), (0.78, 0.20), (0.78, 0.62), (0.40, 0.62),
           (0.40, 0.40), (0.62, 0.40)]
maze_pts = [left_face(u, v) for u, v in maze_uv]

# Flecha en la cara derecha -------------------------------------------------
arrow_uv = [(0.14, 0.86), (0.40, 0.80), (0.66, 0.60), (0.80, 0.38)]
arrow_pts = [right_face(u, v) for u, v in arrow_uv]
# punta: prolongar la direccion final
_dx = arrow_pts[-1][0] - arrow_pts[-2][0]
_dy = arrow_pts[-1][1] - arrow_pts[-2][1]
_len = math.hypot(_dx, _dy)
_dir = (_dx / _len, _dy / _len)
_perp = (-_dir[1], _dir[0])
tip = (arrow_pts[-1][0] + _dir[0] * 26, arrow_pts[-1][1] + _dir[1] * 26)
head = [
    tip,
    (arrow_pts[-1][0] + _perp[0] * 14, arrow_pts[-1][1] + _perp[1] * 14),
    (arrow_pts[-1][0] - _perp[0] * 14, arrow_pts[-1][1] - _perp[1] * 14),
]

hex_outline = [T, TR, BR, B, BL, TL]
inner_edges = [(C, T), (C, B), (C, TL), (C, TR)]
# nota: C-T no es arista visible del cubo; las visibles son C-TL, C-TR, C-B
inner_edges = [(C, TL), (C, TR), (C, B)]

EDGE_W = 6.5
INSET_EDGE_W = 4.5
MAZE_W = 9.0
ARROW_OUT_W = 15.0
ARROW_IN_W = 8.0


# ----------------------------------------------------------------------- svg

def fmt_pts(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def build_svg():
    p = []
    p.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-115 -115 230 230">'
    )
    faces = [
        (top_left_tri, COLORS["top_l"]), (top_right_tri, COLORS["top_r"]),
        (left_up_tri, COLORS["left_u"]), (left_low_tri, COLORS["left_d"]),
        (right_up_tri, COLORS["right_u"]), (right_low_tri, COLORS["right_d"]),
    ]
    for pts, color in faces:
        p.append(f'<polygon points="{fmt_pts(pts)}" fill="{color}"/>')
    # aristas
    for a, b in inner_edges:
        p.append(
            f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
            f'stroke="{COLORS["edge"]}" stroke-width="{EDGE_W}" stroke-linecap="round"/>'
        )
    p.append(
        f'<polygon points="{fmt_pts(hex_outline)}" fill="none" '
        f'stroke="{COLORS["edge"]}" stroke-width="{EDGE_W}" stroke-linejoin="round"/>'
    )
    # inset superior (caja abierta)
    p.append(f'<polygon points="{fmt_pts(inset_left)}" fill="{COLORS["inset_l"]}"/>')
    p.append(f'<polygon points="{fmt_pts(inset_right)}" fill="{COLORS["inset_r"]}"/>')
    p.append(
        f'<polygon points="{fmt_pts(inset)}" fill="none" '
        f'stroke="{COLORS["edge"]}" stroke-width="{INSET_EDGE_W}" stroke-linejoin="round"/>'
    )
    # laberinto
    maze_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in maze_pts)
    p.append(
        f'<path d="{maze_d}" fill="none" stroke="{COLORS["edge"]}" '
        f'stroke-width="{MAZE_W}" stroke-linecap="square" stroke-linejoin="miter"/>'
    )
    # flecha (contorno blanco + relleno verde)
    arrow_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in arrow_pts)
    head_out = scale_about(head, arrow_pts[-1], 1.45)
    p.append(
        f'<path d="{arrow_d}" fill="none" stroke="{COLORS["edge"]}" '
        f'stroke-width="{ARROW_OUT_W}" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    p.append(
        f'<polygon points="{fmt_pts(head_out)}" fill="{COLORS["edge"]}" '
        f'stroke="{COLORS["edge"]}" stroke-width="6" stroke-linejoin="round"/>'
    )
    p.append(
        f'<path d="{arrow_d}" fill="none" stroke="{COLORS["arrow"]}" '
        f'stroke-width="{ARROW_IN_W}" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    p.append(f'<polygon points="{fmt_pts(head)}" fill="{COLORS["arrow"]}"/>')
    p.append("</svg>")
    return "\n".join(p)


# ------------------------------------------------------------------------ png

def build_png(size=1024, ss=4):
    """Renderiza la misma geometria con Pillow (supermuestreado)."""
    big = size * ss
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def tx(p):
        # viewBox -115..115 -> 0..big
        return ((p[0] + 115) / 230 * big, (p[1] + 115) / 230 * big)

    def w(units):
        return max(1, round(units / 230 * big))

    def poly(pts, fill=None, outline=None, width=1):
        d.polygon([tx(p) for p in pts], fill=fill, outline=outline, width=width)

    def stroke(pts, color, width, closed=False):
        seq = [tx(p) for p in pts]
        if closed:
            seq.append(seq[0])
        d.line(seq, fill=color, width=w(width), joint="curve")
        r = w(width) / 2
        for p in (seq[0], seq[-1]):
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)

    for pts, color in [
        (top_left_tri, COLORS["top_l"]), (top_right_tri, COLORS["top_r"]),
        (left_up_tri, COLORS["left_u"]), (left_low_tri, COLORS["left_d"]),
        (right_up_tri, COLORS["right_u"]), (right_low_tri, COLORS["right_d"]),
    ]:
        poly(pts, fill=color)

    for a, b in inner_edges:
        stroke([a, b], COLORS["edge"], EDGE_W)
    stroke(hex_outline, COLORS["edge"], EDGE_W, closed=True)

    poly(inset_left, fill=COLORS["inset_l"])
    poly(inset_right, fill=COLORS["inset_r"])
    stroke(inset, COLORS["edge"], INSET_EDGE_W, closed=True)

    stroke(maze_pts, COLORS["edge"], MAZE_W)

    head_out = scale_about(head, arrow_pts[-1], 1.45)
    stroke(arrow_pts, COLORS["edge"], ARROW_OUT_W)
    poly(head_out, fill=COLORS["edge"])
    stroke(arrow_pts, COLORS["arrow"], ARROW_IN_W)
    poly(head, fill=COLORS["arrow"])

    return img.resize((size, size), Image.LANCZOS)


def build_splash(logo_png):
    """Pantalla de carga nativa (PyInstaller --splash): visible al instante."""
    from PIL import ImageFont

    w, h = 440, 260
    img = Image.new("RGBA", (w, h), (20, 24, 29, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(44, 53, 64, 255), width=2)
    logo = logo_png.resize((120, 120), Image.LANCZOS)
    img.paste(logo, ((w - 120) // 2, 34), logo)
    try:
        font_b = ImageFont.truetype("segoeuib.ttf", 24)
        font_s = ImageFont.truetype("segoeui.ttf", 13)
    except OSError:
        font_b = font_s = ImageFont.load_default()

    def center(text, y, font, fill):
        tw = d.textlength(text, font=font)
        d.text(((w - tw) / 2, y), text, font=font, fill=fill)

    center("PURE LAUNCHER", 168, font_b, (237, 242, 246, 255))
    center("Cargando…", 206, font_s, (141, 154, 167, 255))
    return img.convert("RGB")


def main():
    svg = build_svg()
    with open(os.path.join(ROOT, "ui", "logo.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    png = build_png()
    png.save(os.path.join(HERE, "logo.png"))
    png.save(
        os.path.join(HERE, "icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    build_splash(png).save(os.path.join(HERE, "splash.png"))
    print("assets generados: ui/logo.svg, assets/logo.png, assets/icon.ico, assets/splash.png")


if __name__ == "__main__":
    main()
