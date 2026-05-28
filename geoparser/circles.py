import re
from typing import Any, Dict, List

from geoparser.vertices import eval_expr

# ============================================================
# Circle parsing
# ============================================================

CIRCLE_RE = re.compile(
    r'circle\s+([A-Za-z][A-Za-z0-9_]*)\s+center\s+([A-Za-z][A-Za-z0-9_]*)'
    r'\s+radius\s+([^,\n]+?)(?:\s+fill\s+([A-Za-z!0-9]+))?$',
    re.IGNORECASE | re.MULTILINE
)


def parse_circles(text: str) -> List[Dict[str, Any]]:
    """
    Parse circle declarations from text.

    Input example:
        "circle C1 center O radius 3"
        "circle C2 center P radius sqrt(2) fill blue"

    Returns a list of dicts:
        [
            {'name': 'C1', 'center': 'O', 'radius': 3.0, 'fill': None},
            {'name': 'C2', 'center': 'P', 'radius': 1.414..., 'fill': 'blue'},
        ]
    """
    circles: List[Dict[str, Any]] = []

    for m in CIRCLE_RE.finditer(text):
        circles.append({
            "name":   m.group(1),
            "center": m.group(2),
            "radius": eval_expr(m.group(3).strip()),
            "fill":   m.group(4),          # None if not present
        })

    return circles