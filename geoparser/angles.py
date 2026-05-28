import re
import math
from typing import Dict, List, Tuple

# ============================================================
# Angle parsing + TikZ rendering helpers
# ============================================================

ANGLE_EQ_RE = re.compile(
    r'\b([A-Z]{3})\s*=\s*([-0-9.]+)\b',
    re.IGNORECASE
)

ANGLE_IS_RE = re.compile(
    r'angle\s+([A-Z]{3})\s*(?:is|=)\s*([-0-9.]+)\s*(?:degrees?|°)?',
    re.IGNORECASE
)

RIGHT_ANGLE_RE_1 = re.compile(
    r'angle\s+([A-Z]{3})\s+is\s+a\s+right\s+angle',
    re.IGNORECASE
)

RIGHT_ANGLE_RE_2 = re.compile(
    r'right angle\s+([A-Z]{3})',
    re.IGNORECASE
)


# -------------------------
# Parsing
# -------------------------

def parse_angles(text: str) -> List[Tuple[str, str, str, float]]:
    """
    Parse angle declarations from text.

    Recognises:
        ABC=60          → angle ABC is 60°
        angle ABC is 60 → angle ABC is 60°
        angle ABC is a right angle
        right angle ABC

    Returns:
        [(p1, vertex, p2, degrees), ...]
        e.g. [('A', 'B', 'C', 60.0), ('B', 'D', 'C', 90.0)]
    """
    angle_map: Dict[str, float] = {}

    for m in ANGLE_EQ_RE.finditer(text):
        angle_map[m.group(1).upper()] = float(m.group(2))

    for m in ANGLE_IS_RE.finditer(text):
        angle_map[m.group(1).upper()] = float(m.group(2))

    for m in RIGHT_ANGLE_RE_1.finditer(text):
        angle_map[m.group(1).upper()] = 90.0

    for m in RIGHT_ANGLE_RE_2.finditer(text):
        angle_map[m.group(1).upper()] = 90.0

    return [
        (ang[0], ang[1], ang[2], deg)
        for ang, deg in angle_map.items()
        if len(ang) == 3
    ]


# -------------------------
# Geometry helpers
# -------------------------

def _normalize(dx: float, dy: float) -> Tuple[float, float]:
    norm = math.hypot(dx, dy)
    if norm == 0:
        return (0.0, 0.0)
    return (dx / norm, dy / norm)


def ccw_angle_measure(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    v: str,
    p2: str,
) -> float:
    """
    Return the counterclockwise angle (in degrees) from ray v→p1 to ray v→p2.
    """
    x1, y1 = vertices[p1]
    xv, yv = vertices[v]
    x2, y2 = vertices[p2]

    a1 = math.degrees(math.atan2(y1 - yv, x1 - xv))
    a2 = math.degrees(math.atan2(y2 - yv, x2 - xv))
    return (a2 - a1) % 360


def choose_angle_order(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    v: str,
    p2: str,
    deg: float,
) -> Tuple[str, str]:
    """
    Return the point order whose CCW angle best matches ``deg``.
    Needed so that TikZ's pic angle draws the correct arc direction.
    """
    forward = ccw_angle_measure(vertices, p1, v, p2)
    backward = ccw_angle_measure(vertices, p2, v, p1)

    if abs(forward - deg) <= abs(backward - deg):
        return p1, p2
    return p2, p1


# -------------------------
# TikZ rendering
# -------------------------

def right_angle_marker_code(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    v: str,
    p2: str,
    size: float = 0.35,
    label: str = None,
) -> List[str]:
    """
    Return TikZ lines that draw a small square right-angle marker at
    vertex ``v`` for the angle p1–v–p2.

    Optionally adds a text ``label`` (e.g. "90°") near the marker.
    """
    from geoparser.renderer import tikz_num  # local import to avoid circular deps

    x1, y1 = vertices[p1]
    xv, yv = vertices[v]
    x2, y2 = vertices[p2]

    u1x, u1y = _normalize(x1 - xv, y1 - yv)
    u2x, u2y = _normalize(x2 - xv, y2 - yv)

    ax, ay = xv + size * u1x, yv + size * u1y
    bx, by = ax + size * u2x, ay + size * u2y
    cx, cy = xv + size * u2x, yv + size * u2y

    lines = [
        rf"\draw ({tikz_num(ax)},{tikz_num(ay)}) -- "
        rf"({tikz_num(bx)},{tikz_num(by)}) -- "
        rf"({tikz_num(cx)},{tikz_num(cy)});"
    ]

    if label is not None:
        lx = xv + 1.6 * size * (u1x + u2x)
        ly = yv + 1.6 * size * (u1y + u2y)
        lines.append(
            rf"\node at ({tikz_num(lx)},{tikz_num(ly)}) {{$ {label} $}};"
        )

    return lines