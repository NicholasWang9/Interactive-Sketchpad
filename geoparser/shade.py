import re
from typing import Any, Dict, List, Tuple

from geoparser.arcs import arc_path_fragment

# ============================================================
# Shaded-region parsing + TikZ rendering
# ============================================================

SHADE_RE = re.compile(
    r'shade\s+(.+?)(?:\s+fill\s+([A-Za-z!0-9]+))?$',
    re.IGNORECASE | re.MULTILINE
)

SHADE_TOKEN_RE = re.compile(
    r'([A-Z]{2}|[A-Z]{3})(?:\[(above|below|left|right|cw|ccw|minor)\])?',
    re.IGNORECASE
)


# -------------------------
# Parsing
# -------------------------

def parse_shaded_regions(text: str) -> List[Dict[str, Any]]:
    """
    Parse shaded-region declarations.

    Examples:
        shade DAB BCD
        shade DAB BCD fill gray!50
        shade AB BC CA fill blue!20

    Returns:
        [
            {
                "tokens": ["DAB", "BCD"],
                "fill": "gray!50"
            }
        ]
    """
    shaded: List[Dict[str, Any]] = []

    for match in SHADE_RE.finditer(text):
        path_text = match.group(1).strip()
        fill = match.group(2) or "gray!30"

        tokens = path_text.split()

        shaded.append({
            "tokens": tokens,
            "fill": fill,
        })

    return shaded


# -------------------------
# Token helpers
# -------------------------

def parse_shade_token(token: str) -> Tuple[str, str]:
    """
    Parse one shade-path token.

    Returns:
        (base_token, mode)

    Examples:
        "AB" -> ("AB", "minor")
        "DAB" -> ("DAB", "minor")
        "YBO[right]" -> ("YBO", "right")
    """
    token = token.strip()
    m = SHADE_TOKEN_RE.fullmatch(token)

    if not m:
        raise ValueError(f"Invalid shade token: {token}")

    base = m.group(1).upper()
    mode = (m.group(2) or "minor").lower()

    return base, mode


def token_start_point(token: str) -> str:
    """
    Return the starting point of a path token.

    AB   -> A
    DAB  -> D
    """
    base, _ = parse_shade_token(token)
    return base[0]


def token_end_point(token: str) -> str:
    """
    Return the ending point of a path token.

    AB   -> B
    DAB  -> B
    """
    base, _ = parse_shade_token(token)

    if len(base) == 2:
        return base[1]

    return base[2]


def token_path_fragment(
    vertices: Dict[str, Tuple[float, float]],
    token: str,
) -> str:
    """
    Convert a shade token into a TikZ path fragment.

    AB         -> -- (B)
    DAB        -> arc[...]
    YBO[right] -> arc[...]
    """
    base, mode = parse_shade_token(token)

    if len(base) == 2:
        a, b = base[0], base[1]
        return rf"-- ({b})"

    if len(base) == 3:
        p1, center, p2 = base[0], base[1], base[2]
        return arc_path_fragment(vertices, p1, center, p2, mode)

    raise ValueError(f"Unsupported shade token: {token}")


# -------------------------
# TikZ rendering
# -------------------------

def shaded_region_code(
    vertices: Dict[str, Tuple[float, float]],
    region: Dict[str, Any],
) -> str:
    """
    Convert one shaded region into a TikZ \\fill command.
    """
    tokens = region["tokens"]
    fill = region.get("fill", "gray!30")

    if not tokens:
        return ""

    # Start at the start point of the first token
    start = token_start_point(tokens[0])

    parts = [rf"\fill[{fill}] ({start})"]

    for token in tokens:
        parts.append(token_path_fragment(vertices, token))

    parts.append(r"-- cycle;")

    return "\n  ".join(parts)