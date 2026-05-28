"""
geoparser
=========
Convert plain-text geometry descriptions into compilable LaTeX/TikZ diagrams.

Quickstart::

    from geoparser import geometry_to_latex

    tex = geometry_to_latex('''
        A is at (0, 0)
        B is at (4, 0)
        C is at (2, 3)
        line segments AB BC CA
    ''')
    print(tex)
"""

from geoparser.converter import geometry_to_latex
from geoparser.parser    import parse_geometry
from geoparser.renderer  import generate_tikz, make_tex_document

__all__ = [
    "geometry_to_latex",
    "parse_geometry",
    "generate_tikz",
    "make_tex_document",
]