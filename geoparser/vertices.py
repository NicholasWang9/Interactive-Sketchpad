import re
import math
from collections import defaultdict
from typing import Dict, List, Tuple

# ============================================================
# Vertex parsing + label positioning
# ============================================================

VERTEX_RE = re.compile(
    r'([A-Z])\s*(?:is at|at)?\s*\(\s*([^,]+)\s*,\s*(.+)\s*\)',
    re.IGNORECASE
)

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


def parse_vertices(text: str) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, str]]:
    """
    Parse vertex coordinates and optional manual label positions.

    Returns:
        vertices:        {'A': (0.0, 0.0), 'B': (3.0, 4.0), ...}
        label_positions: {'A': 'above left', ...}  (only explicitly overridden ones)
    """
    vertices: Dict[str, Tuple[float, float]] = {}
    label_positions: Dict[str, str] = {}

    for match in VERTEX_RE.finditer(text):
        name = match.group(1).upper()
        x = eval_expr(match.group(2).strip())
        y = eval_expr(match.group(3).strip())
        vertices[name] = (x, y)

    for match in LABEL_POS_RE.finditer(text):
        pt = match.group(1).upper()
        pos = match.group(2).lower()
        label_positions[pt] = pos

    return vertices, label_positions


# -------------------------
# Label-position helpers
# -------------------------

def _build_adjacency(segments: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    adj = defaultdict(list)
    for a, b in segments:
        adj[a].append(b)
        adj[b].append(a)
    return adj


def _normalize(dx: float, dy: float) -> Tuple[float, float]:
    norm = math.hypot(dx, dy)
    if norm == 0:
        return (0.0, 0.0)
    return (dx / norm, dy / norm)


def vector_to_tikz_position(dx: float, dy: float) -> str:
    """
    Convert a direction vector into a TikZ node position string
    (e.g. 'above right', 'below left', 'left').
    """
    thresh = 0.35
    horiz = "right" if dx > thresh else ("left" if dx < -thresh else "")
    vert = "above" if dy > thresh else ("below" if dy < -thresh else "")

    if vert and horiz:
        return f"{vert} {horiz}"
    return vert or horiz or "above right"


def auto_label_position(
    name: str,
    vertices: Dict[str, Tuple[float, float]],
    segments: List[Tuple[str, str]],
) -> str:
    """
    Choose a label position automatically based on the directions of
    incident edges. The label is placed opposite the average neighbour
    direction so it doesn't overlap the segments.
    """
    if name not in vertices:
        return "above right"

    x, y = vertices[name]
    adj = _build_adjacency(segments)
    nbrs = adj.get(name, [])

    if not nbrs:
        # Isolated point: push label away from the centroid
        xs = [p[0] for p in vertices.values()]
        ys = [p[1] for p in vertices.values()]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        return vector_to_tikz_position(x - cx, y - cy)

    vx, vy = 0.0, 0.0
    for nbr in nbrs:
        if nbr not in vertices:
            continue
        xn, yn = vertices[nbr]
        ux, uy = _normalize(xn - x, yn - y)
        vx += ux
        vy += uy

    return vector_to_tikz_position(-vx, -vy)