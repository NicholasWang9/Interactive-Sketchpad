from geoparser.parser   import parse_geometry
from geoparser.renderer import generate_tikz, make_tex_document

# ============================================================
# Top-level converter
# ============================================================


def geometry_to_latex(text: str) -> str:
    """
    Convert a plain-text geometry description into a compilable LaTeX
    document containing a TikZ diagram.

    Args:
        text: Free-form geometry description.  See the prompt template
              in main.py for the expected format.

    Returns:
        A complete LaTeX document string (ready to pass to pdflatex).

    Example::

        from geoparser import geometry_to_latex

        tex = geometry_to_latex('''
            A is at (0, 0)
            B is at (4, 0)
            C is at (2, 3)
            line segments AB BC CA
        ''')
        print(tex)
    """
    vertices, segments, angles, label_positions, circles, arcs = parse_geometry(text)
    tikz = generate_tikz(vertices, segments, angles, label_positions, circles, arcs)
    return make_tex_document(tikz)