import math
from typing import Any, Dict, List, Tuple

from geoparser.vertices import auto_label_position
from geoparser.angles import right_angle_marker_code, choose_angle_order
from geoparser.arcs import arc_code

# ============================================================
# TikZ / LaTeX rendering
# ============================================================


# -------------------------
# Low-level helpers
# -------------------------

def tikz_num(x: float) -> str:
    """
    Format a float for TikZ: strip trailing zeros, collapse -0 → 0.
    """
    if abs(x) < 1e-10:
        x = 0.0
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def normalize(dx: float, dy: float) -> Tuple[float, float]:
    """Return the unit vector for (dx, dy)."""
    norm = math.hypot(dx, dy)
    if norm == 0:
        return (0.0, 0.0)
    return (dx / norm, dy / norm)


# -------------------------
# Main TikZ builder
# -------------------------

def generate_tikz(
    vertices:        Dict[str, Tuple[float, float]],
    segments:        List[Tuple[str, str]],
    angles:          List[Tuple[str, str, str, float]],
    label_positions: Dict[str, str],
    circles:         List[Dict[str, Any]],
    arcs:            List[Tuple[str, str, str, str]],
) -> str:
    """
    Convert structured geometry data into a TikZ picture string.
    """
    lines: List[str] = []
    lines.append(r"\begin{tikzpicture}[scale=1]")

    # -- coordinate declarations --
    for name, (x, y) in vertices.items():
        lines.append(rf"\coordinate ({name}) at ({tikz_num(x)},{tikz_num(y)});")

    # -- circles --
    for circle in circles:
        center = circle["center"]
        if center not in vertices:
            continue
        r    = tikz_num(circle["radius"])
        fill = circle.get("fill")
        if fill:
            lines.append(
                rf"\filldraw[fill={fill}, draw=black] ({center}) circle ({r});"
            )
        else:
            lines.append(rf"\draw ({center}) circle ({r});")

    # -- points + labels --
    for name in vertices:
        lines.append(rf"\fill ({name}) circle (2pt);")
        pos = label_positions.get(
            name,
            auto_label_position(name, vertices, segments)
        )
        lines.append(rf"\node[{pos}] at ({name}) {{$ {name} $}};")

    # -- segments --
    for a, b in segments:
        if a in vertices and b in vertices:
            lines.append(rf"\draw ({a}) -- ({b});")

    # -- arcs --
    for p1, center, p2, mode in arcs:
        if all(pt in vertices for pt in (p1, center, p2)):
            lines.append(arc_code(vertices, p1, center, p2, mode))

    # -- angle markers --
    for p1, v, p2, deg in angles:
        if not all(pt in vertices for pt in (p1, v, p2)):
            continue

        p1d, p2d = choose_angle_order(vertices, p1, v, p2, deg)

        if abs(deg - 90.0) < 1e-9:
            lines.extend(
                right_angle_marker_code(vertices, p1d, v, p2d, size=0.35)
            )
        else:
            lines.append(
                rf'\pic [draw, angle radius=8mm, angle eccentricity=1.35, '
                rf'"$ {deg:g}^\circ $"] '
                rf'{{angle = {p1d}--{v}--{p2d}}};'
            )

    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


# -------------------------
# LaTeX document wrapper
# -------------------------

def make_tex_document(tikz_code: str) -> str:
    """
    Wrap a TikZ snippet in a minimal, compilable LaTeX document.
    """
    return rf"""
\documentclass{{article}}

\usepackage{{tikz}}
\usetikzlibrary{{angles,quotes}}

\begin{{document}}

\centering

{tikz_code}

\end{{document}}
"""