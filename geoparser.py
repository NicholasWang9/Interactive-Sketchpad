import re
import math
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# ============================================================
# Geometry -> TikZ LaTeX Renderer
# Supports:
# - coordinates with expressions
# - line segments
# - angle labels
# - right angle markers
# - automatic point-label positioning
# ============================================================

VERTEX_RE = re.compile(
    r'([A-Z])\s*(?:is at|at)?\s*\(\s*([^,]+)\s*,\s*(.+)\s*\)',
    re.IGNORECASE
)


SEGMENT_RE = re.compile(
    r'line segments?\s*:?\s*([A-Z,\s]+)',
    re.IGNORECASE
)

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

CIRCLE_RE = re.compile(
    r'circle\s+([A-Za-z][A-Za-z0-9_]*)\s+center\s+([A-Za-z][A-Za-z0-9_]*)\s+radius\s+([^,\n]+)(?:\s+fill\s+([A-Za-z!0-9]+))?',
    re.IGNORECASE
)

ARC_RE = re.compile(
    r'arcs?\s*:?\s*([A-Z,\s]+)',
    re.IGNORECASE
)

# Optional manual label override, e.g.
# "P label above left"
LABEL_POS_RE = re.compile(
    r'([A-Z])\s+label\s+(above left|above right|below left|below right|above|below|left|right)',
    re.IGNORECASE
)

SAFE_MATH = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
}


def eval_expr(expr: str) -> float:
    """
    Safely evaluate simple math expressions.
    Examples:
      3*sqrt(3)
      pi/2
      sin(pi/3)
    """
    return float(eval(expr, {"__builtins__": {}}, SAFE_MATH))


def tikz_num(x: float) -> str:
    """
    Clean number formatting for TikZ.
    """
    if abs(x) < 1e-10:
        x = 0.0
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def normalize(dx: float, dy: float) -> Tuple[float, float]:
    """
    Return the normalized version of a 2D vector.
    """
    norm = math.hypot(dx, dy)
    if norm == 0:
        return (0.0, 0.0)
    return (dx / norm, dy / norm)


def parse_geometry(text: str):
    """
    Returns:
        vertices: dict like {'A': (0,0), 'B': (3,2)}
        segments: list like [('A','B'), ('B','C')]
        angles:   list like [('B','A','C', 60.0), ('B','D','C', 90.0)]
                  meaning angle BAC = 60, angle BDC = 90
    """
    vertices: Dict[str, Tuple[float, float]] = {}
    segments: List[Tuple[str, str]] = []
    angle_map: Dict[str, float] = {}
    label_positions: Dict[str, str] = {}
    circles: List[Dict[str, Any]] = []
    arcs: List[Tuple[str, str, str]] = []

    # -------------------------
    # Parse vertices
    # -------------------------
    for match in VERTEX_RE.finditer(text):
        name = match.group(1).upper()
        x_expr = match.group(2).strip()
        y_expr = match.group(3).strip()

        x = eval_expr(x_expr)
        y = eval_expr(y_expr)

        vertices[name] = (x, y)

    # -------------------------
    # Parse segments
    # -------------------------
    seg_match = SEGMENT_RE.search(text)
    if seg_match:
        raw = re.split(r'[\s,]+', seg_match.group(1).strip())
        for token in raw:
            token = token.strip().upper()
            if len(token) == 2:
                segments.append((token[0], token[1]))

    # -------------------------
    # Parse angles
    # -------------------------
    for match in ANGLE_EQ_RE.finditer(text):
        ang = match.group(1).upper()
        deg = float(match.group(2))
        angle_map[ang] = deg

    for match in ANGLE_IS_RE.finditer(text):
        ang = match.group(1).upper()
        deg = float(match.group(2))
        angle_map[ang] = deg

    for match in RIGHT_ANGLE_RE_1.finditer(text):
        ang = match.group(1).upper()
        angle_map[ang] = 90.0

    for match in RIGHT_ANGLE_RE_2.finditer(text):
        ang = match.group(1).upper()
        angle_map[ang] = 90.0

    angles: List[Tuple[str, str, str, float]] = []
    for ang, deg in angle_map.items():
        if len(ang) == 3:
            angles.append((ang[0], ang[1], ang[2], deg))

    # -------------------------
    # Optional manual label positions
    # -------------------------
    for match in LABEL_POS_RE.finditer(text):
        pt = match.group(1).upper()
        pos = match.group(2).lower()
        label_positions[pt] = pos

    # -------------------------
    # Parse circles
    # -------------------------
    for match in CIRCLE_RE.finditer(text):
        circle_name = match.group(1)
        center = match.group(2)
        radius_expr = match.group(3).strip()
        fill = match.group(4)

        radius = eval_expr(radius_expr)

        circles.append({
            "name": circle_name,
            "center": center,
            "radius": radius,
            "fill": fill,
        })
    
    # -------------------------
    # Parse arcs
    # Example: arcs BCD BAD
    # BCD means arc from B to D centered at C
    # BAD means arc from B to D centered at A
    # -------------------------
    arc_match = ARC_RE.search(text)

    if arc_match:
        raw = re.split(r'[\s,]+', arc_match.group(1).strip())

        for token in raw:
            token = token.strip().upper()

            if len(token) == 3:
                p1 = token[0]
                center = token[1]
                p2 = token[2]

                arcs.append((p1, center, p2))

    return vertices, segments, angles, label_positions, circles, arcs


def build_adjacency(segments: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    """
    Build a graph showing which points are connected by segments.
    """
    adj = defaultdict(list)
    for a, b in segments:
        adj[a].append(b)
        adj[b].append(a)
    return adj


def vector_to_tikz_position(dx: float, dy: float) -> str:
    """
    Convert a direction vector into a TikZ node position string.
    """
    thresh = 0.35

    horiz = ""
    vert = ""

    if dx > thresh:
        horiz = "right"
    elif dx < -thresh:
        horiz = "left"

    if dy > thresh:
        vert = "above"
    elif dy < -thresh:
        vert = "below"

    if vert and horiz:
        return f"{vert} {horiz}"
    if vert:
        return vert
    if horiz:
        return horiz
    return "above right"


def auto_label_position(
    name: str,
    vertices: Dict[str, Tuple[float, float]],
    segments: List[Tuple[str, str]]
) -> str:
    """
    Choose a label position automatically based on the directions
    of incident edges. The label is placed opposite the average
    direction of connected segments.
    """
    adj = build_adjacency(segments)

    if name not in vertices:
        return "above right"

    x, y = vertices[name]
    nbrs = adj.get(name, [])

    # If isolated, fall back to center-based heuristic
    if not nbrs:
        xs = [p[0] for p in vertices.values()]
        ys = [p[1] for p in vertices.values()]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        return vector_to_tikz_position(x - cx, y - cy)

    vx = 0.0
    vy = 0.0

    for nbr in nbrs:
        if nbr not in vertices:
            continue
        xn, yn = vertices[nbr]
        ux, uy = normalize(xn - x, yn - y)
        vx += ux
        vy += uy

    # Put label opposite the "crowded" direction
    return vector_to_tikz_position(-vx, -vy)


def right_angle_marker_code(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    v: str,
    p2: str,
    size: float = 0.35,
    label: str = None
) -> List[str]:
    """
    Draw a little square marking a right angle at vertex v
    for angle p1-v-p2. Optionally adds a label like 90°.
    """
    x1, y1 = vertices[p1]
    xv, yv = vertices[v]
    x2, y2 = vertices[p2]

    u1x, u1y = normalize(x1 - xv, y1 - yv)
    u2x, u2y = normalize(x2 - xv, y2 - yv)

    ax = xv + size * u1x
    ay = yv + size * u1y

    bx = ax + size * u2x
    by = ay + size * u2y

    cx = xv + size * u2x
    cy = yv + size * u2y

    lines = []
    lines.append(
        rf"\draw ({tikz_num(ax)},{tikz_num(ay)}) -- "
        rf"({tikz_num(bx)},{tikz_num(by)}) -- "
        rf"({tikz_num(cx)},{tikz_num(cy)});"
    )

    if label is not None:
        lx = xv + 1.6 * size * (u1x + u2x)
        ly = yv + 1.6 * size * (u1y + u2y)
        lines.append(
            rf"\node at ({tikz_num(lx)},{tikz_num(ly)}) {{$ {label} $}};"
        )

    return lines

def ccw_angle_measure(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    v: str,
    p2: str
) -> float:
    """
    Return the counterclockwise angle from ray v->p1 to ray v->p2 in degrees.
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
    deg: float
) -> Tuple[str, str]:
    """
    Choose the point order whose counterclockwise angle best matches the given degree measure.
    """
    forward = ccw_angle_measure(vertices, p1, v, p2)
    backward = ccw_angle_measure(vertices, p2, v, p1)

    if abs(forward - deg) <= abs(backward - deg):
        return p1, p2

    return p2, p1

def distance_between(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    p2: str
) -> float:
    """
    Return the distance between two points."""
    x1, y1 = vertices[p1]
    x2, y2 = vertices[p2]

    return math.hypot(x2 - x1, y2 - y1)


def angle_of_point_around_center(
    vertices: Dict[str, Tuple[float, float]],
    point: str,
    center: str
) -> float:
    """
    Return the polar angle of a point around a center in degrees.
    """
    xp, yp = vertices[point]
    xc, yc = vertices[center]

    return math.degrees(math.atan2(yp - yc, xp - xc))


def minor_arc_angles(start_angle: float, end_angle: float) -> Tuple[float, float]:
    """
    Return start/end angles that make TikZ draw the minor arc.
    """
    delta = (end_angle - start_angle) % 360

    # Convert delta to signed shortest turn in [-180, 180]
    if delta > 180:
        delta -= 360

    return start_angle, start_angle + delta


def arc_code(
    vertices: Dict[str, Tuple[float, float]],
    p1: str,
    center: str,
    p2: str
) -> str:
    """
    Generate TikZ code for the minor arc from p1 to p2 centered at center.
    """
    radius = distance_between(vertices, center, p1)

    start_angle = angle_of_point_around_center(vertices, p1, center)
    end_angle = angle_of_point_around_center(vertices, p2, center)

    start_angle, end_angle = minor_arc_angles(start_angle, end_angle)

    return (
        rf"\draw ({center}) ++({tikz_num(start_angle)}:{tikz_num(radius)}) "
        rf"arc ({tikz_num(start_angle)}:{tikz_num(end_angle)}:{tikz_num(radius)});"
    )

def generate_tikz(
    vertices: Dict[str, Tuple[float, float]],
    segments: List[Tuple[str, str]],
    angles: List[Tuple[str, str, str, float]],
    label_positions: Dict[str, str],
    circles: List[Dict[str, Any]],
    arcs: List[Tuple[str, str, str]]
):
    """
    Convert structured geometry into TikZ drawing code.
    """
    lines = []
    lines.append(r"\begin{tikzpicture}[scale=1]")

    # coordinates
    for name, (x, y) in vertices.items():
        lines.append(rf"\coordinate ({name}) at ({tikz_num(x)},{tikz_num(y)});")
    
    # circles
    for circle in circles:
        center = circle["center"]
        radius = circle["radius"]
        fill = circle.get("fill")

        if center not in vertices:
            continue

        if fill:
            lines.append(
                rf"\filldraw[fill={fill}, draw=black] ({center}) circle ({tikz_num(radius)});"
            )
        else:
            lines.append(
                rf"\draw ({center}) circle ({tikz_num(radius)});"
            )

    # points + labels
    for name in vertices:
        lines.append(rf"\fill ({name}) circle (2pt);")

        pos = label_positions.get(
            name,
            auto_label_position(name, vertices, segments)
        )

        lines.append(
            rf"\node[{pos}] at ({name}) {{$ {name} $}};"
        )

    # segments
    for a, b in segments:
        if a not in vertices or b not in vertices:
            continue
        lines.append(rf"\draw ({a}) -- ({b});")
    
    # arcs
    for p1, center, p2 in arcs:
        if p1 not in vertices or center not in vertices or p2 not in vertices:
            continue

        lines.append(
            arc_code(vertices, p1, center, p2)
        )

    # angles
    for p1, v, p2, deg in angles:
        if p1 not in vertices or v not in vertices or p2 not in vertices:
            continue

        # Pick the order that matches the intended angle measure.
        # Example: ECF=45 may need to become F--C--E in TikZ.
        p1_draw, p2_draw = choose_angle_order(vertices, p1, v, p2, deg)

        if abs(deg - 90.0) < 1e-9:
            lines.extend(
                right_angle_marker_code(
                    vertices,
                    p1_draw, v, p2_draw,
                    size=0.35,
                    label=None
                )
            )
        else:
            lines.append(
                rf'\pic [draw, angle radius=8mm, angle eccentricity=1.35, "$ {deg:g}^\circ $"] '
                rf'{{angle = {p1_draw}--{v}--{p2_draw}}};'
            )

    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def make_tex_document(tikz_code: str):
    """
    Wrap TikZ code into runnable LaTeX.
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


def geometry_to_latex(chatgpt_text: str):
    """
    Convert geometry text descriptions into runnable LaTeX/TikZ code.
    """
    vertices, segments, angles, label_positions, circles, arcs = parse_geometry(chatgpt_text)

    tikz = generate_tikz(
        vertices,
        segments,
        angles,
        label_positions,
        circles,
        arcs
    )

    tex = make_tex_document(tikz)
    return tex


# ============================================================
# Example usage
# ============================================================

example = """
O is at (0,0)
X is at (4,0)
Y is at (0,4)

A is at (2,0)
B is at (0,2)

line segments OX OY

arcs XOY OAX YBO
"""

latex_code = geometry_to_latex(example)
print(latex_code)

'''
When I send you a geometry diagram, convert it into a clean parser-friendly text format.

Your task:
1. Identify all important points/vertices in the diagram.
2. Assign concrete coordinates that preserve the important geometry.
3. Do not use unresolved variables like s, r, a, h, x, etc.
4. If a coordinate depends on a given condition, solve just enough to substitute an exact value.
5. List all visible line segments.
6. List only the angles that are explicitly marked or labeled in the diagram.
7. List all circles/arcs if present, including their centers and radii when possible.
8. Add label positions only when useful to avoid overlap.

Output format exactly:

example = """
[Point] is at ([x-coordinate],[y-coordinate])
[Point] is at ([x-coordinate],[y-coordinate])
...

line segments [AB] [BC] [CD] ...

angles [ABC]=[degree] [DEF]=[degree] ...

circle [CircleName] center [Point] radius [radius]
circle [CircleName] center [Point] radius [radius]

arcs [ABC] [DEF] ...
"""

Rules:
- Output only the `example = """ ... """` block.
- Use Python-style math expressions:
  - `sqrt(3)`, not `sqrt3`
  - `2*sqrt(3)`, not `2sqrt3`
  - `pi`, `sin(pi/3)`, `cos(pi/3)` if needed
- Use exact coordinates when possible.
- Approximate coordinates are okay only if exact coordinates are hard or unnecessary.
- Do not include line segments, vertices, angles, arcs unless they are actually marked or labeled in the diagram.
- Include visible vertices and line segments needed to reproduce the diagram.
- For line segments, use two-letter notation:
  - `AB` means segment from A to B.
- For angles, use three-letter notation:
  - `ABC=60` means angle ABC is 60 degrees, with B as the vertex.
- For arcs, use three-letter notation:
  - `ABC` means arc from A to C centered at B.
  - The middle letter is always the center of the arc.
  - Example: if an arc goes from A to C and is centered at B, write `arcs ABC`.
  - Example: if an arc goes from D to B and is centered at C, write `arcs DCB`.
- Only include arcs that are actually drawn in the diagram.
- For circles, define the center point first:
  - `O is at (0,0)`
  - `circle C1 center O radius 1`
- If a circle center is not labeled, create a reasonable name like O, O1, O2, etc.
- Preserve the visual and geometric structure, not exact pixel positions.
- Do not solve the full problem unless I ask. Only solve enough to create valid coordinates.
'''
