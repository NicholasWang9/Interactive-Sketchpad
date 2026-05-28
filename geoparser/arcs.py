import re
import math
from typing import Dict, List, Tuple

# ============================================================
# Arc parsing + TikZ arc rendering
#
# Arc notation:
#   ABC        = arc from A to C centered at B, default minor arc
#   ABC[above] = arc from A to C centered at B, drawn on the above side
#   ABC[right] = arc from A to C centered at B, drawn on the right side
#   ABC[cw]    = clockwise arc
#   ABC[ccw]   = counterclockwise arc
#
# Examples:
#   arcs XOY OAX[above] YBO[right]
#
# Meaning:
#   XOY         = arc from X to Y centered at O
#   OAX[above] = arc from O to X centered at A, above the diameter
#   YBO[right] = arc from Y to O centered at B, right of the diameter
# ============================================================


ARC_RE = re.compile(
    r'arcs?\s*:?\s*([A-Z\[\]a-z,\s]+)',
    re.IGNORECASE
)

ARC_TOKEN_RE = re.compile(
    r'([A-Z]{3})(?:\[(above|below|left|right|cw|ccw|minor)\])?',
    re.IGNORECASE
)


# -------------------------
# Parsing
# -------------------------

def parse_arcs(text: str) -> List[Tuple[str, str, str, str]]:
    """
    Parse arc declarations from text.

    Each token XYZ means:
        arc from X to Z centered at Y.

    Optional bracket tags control ambiguous arcs:
        XYZ[above]
        XYZ[below]
        XYZ[left]
        XYZ[right]
        XYZ[cw]
        XYZ[ccw]

    Returns:
        [(start, center, end, mode), ...]

    Example:
        "arcs XOY OAX[above] YBO[right]"

    Returns:
        [
            ('X', 'O', 'Y', 'minor'),
            ('O', 'A', 'X', 'above'),
            ('Y', 'B', 'O', 'right'),
        ]
    """
    arcs: List[Tuple[str, str, str, str]] = []

    match = ARC_RE.search(text)
    if not match:
        return arcs

    raw = re.split(r'[\s,]+', match.group(1).strip())

    for token in raw:
        token = token.strip()
        if not token:
            continue

        m = ARC_TOKEN_RE.fullmatch(token)
        if not m:
            continue

        arc_name = m.group(1).upper()
        mode = (m.group(2) or "minor").lower()

        start = arc_name[0]
        center = arc_name[1]
        end = arc_name[2]

        arcs.append((start, center, end, mode))

    return arcs


# -------------------------
# Geometry helpers
# -------------------------

def distance_between(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    p2: str,
) -> float:
    """Return the Euclidean distance between two named vertices."""
    x1, y1 = vertices[p1]
    x2, y2 = vertices[p2]

    return math.hypot(x2 - x1, y2 - y1)


def angle_of_point_around_center(
    vertices: Dict[str, Tuple[float, float]],
    point: str,
    center: str,
) -> float:
    """Return the polar angle of point around center in degrees."""
    xp, yp = vertices[point]
    xc, yc = vertices[center]

    return math.degrees(math.atan2(yp - yc, xp - xc))


def choose_arc_delta(
    start_angle: float,
    end_angle: float,
    mode: str,
) -> float:
    """
    Choose the delta angle for a TikZ arc.

    Positive delta = counterclockwise.
    Negative delta = clockwise.

    mode can be:
        minor, cw, ccw, above, below, left, right
    """
    raw_delta = (end_angle - start_angle) % 360

    # -------------------------
    # Direction modes
    # -------------------------
    if mode == "ccw":
        return raw_delta if raw_delta != 0 else 360

    if mode == "cw":
        return raw_delta - 360 if raw_delta != 0 else -360

    # -------------------------
    # Minor arc mode
    # -------------------------
    if mode == "minor":
        if raw_delta > 180:
            return raw_delta - 360
        return raw_delta

    # -------------------------
    # Side modes:
    # Pick the candidate whose midpoint lies most strongly
    # in the requested direction.
    # -------------------------
    candidates = [
        raw_delta,          # counterclockwise version
        raw_delta - 360,    # clockwise version
    ]

    best_delta = candidates[0]
    best_score = -10**9

    for delta in candidates:
        midpoint_angle = math.radians(start_angle + delta / 2)

        mx = math.cos(midpoint_angle)
        my = math.sin(midpoint_angle)

        if mode == "above":
            score = my
        elif mode == "below":
            score = -my
        elif mode == "right":
            score = mx
        elif mode == "left":
            score = -mx
        else:
            # Unknown mode falls back to minor behavior
            score = -abs(delta)

        if score > best_score:
            best_score = score
            best_delta = delta

    return best_delta


# -------------------------
# TikZ rendering
# -------------------------

def arc_code(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    center: str,
    p2: str,
    mode: str = "minor",
) -> str:
    """
    Return the TikZ draw command for an arc.

    Uses the readable TikZ syntax:

        arc[start angle=..., delta angle=..., radius=...]

    instead of the shorter:

        arc (start:end:radius)

    because delta angle makes direction easier to debug.
    """
    from geoparser.renderer import tikz_num  # local import to avoid circular deps

    radius = distance_between(vertices, center, p1)

    start_angle = angle_of_point_around_center(vertices, p1, center)
    end_angle = angle_of_point_around_center(vertices, p2, center)

    delta = choose_arc_delta(start_angle, end_angle, mode)

    return (
        rf"\draw ({center}) ++({tikz_num(start_angle)}:{tikz_num(radius)}) "
        rf"arc[start angle={tikz_num(start_angle)}, "
        rf"delta angle={tikz_num(delta)}, "
        rf"radius={tikz_num(radius)}];"
    )