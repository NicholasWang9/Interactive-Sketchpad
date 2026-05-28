import re
from collections import defaultdict
from typing import Dict, List, Tuple

# ============================================================
# Line-segment parsing
# ============================================================

SEGMENT_RE = re.compile(
    r'line segments?\s*:?\s*([A-Z,\s]+)',
    re.IGNORECASE
)


def parse_segments(text: str) -> List[Tuple[str, str]]:
    """
    Parse line-segment declarations from text.

    Input example:
        "line segments AB BC CD"

    Returns:
        [('A', 'B'), ('B', 'C'), ('C', 'D')]
    """
    segments: List[Tuple[str, str]] = []

    match = SEGMENT_RE.search(text)
    if match:
        raw = re.split(r'[\s,]+', match.group(1).strip())
        for token in raw:
            token = token.strip().upper()
            if len(token) == 2:
                segments.append((token[0], token[1]))

    return segments


def build_adjacency(segments: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    """
    Build an undirected adjacency list from a list of segments.

    Returns:
        {'A': ['B', 'C'], 'B': ['A'], ...}
    """
    adj: Dict[str, List[str]] = defaultdict(list)
    for a, b in segments:
        adj[a].append(b)
        adj[b].append(a)
    return dict(adj)