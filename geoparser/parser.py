from typing import Any, Dict, List, Tuple

from geoparser.vertices import parse_vertices
from geoparser.segments import parse_segments
from geoparser.angles  import parse_angles
from geoparser.circles import parse_circles
from geoparser.arcs    import parse_arcs

# ============================================================
# Master geometry parser
# ============================================================


def parse_geometry(text: str) -> Tuple[
    Dict[str, Tuple[float, float]],   # vertices
    List[Tuple[str, str]],            # segments
    List[Tuple[str, str, str, float]],# angles
    Dict[str, str],                   # label_positions
    List[Dict[str, Any]],             # circles
    List[Tuple[str, str, str, str]],       # arcs
]:
    """
    Parse a plain-text geometry description into structured data.

    Delegates to the individual sub-parsers and returns a 6-tuple:
        (vertices, segments, angles, label_positions, circles, arcs)

    Each element can be passed directly to ``renderer.generate_tikz()``.
    """
    vertices, label_positions = parse_vertices(text)
    segments                  = parse_segments(text)
    angles                    = parse_angles(text)
    circles                   = parse_circles(text)
    arcs                      = parse_arcs(text)

    return vertices, segments, angles, label_positions, circles, arcs