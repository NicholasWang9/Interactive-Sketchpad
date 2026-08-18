import subprocess
import os
import math
import re

def run_cmd(cmd: list[str], cwd=None) -> None:
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n  {' '.join(cmd)}\n\nOutput:\n{p.stdout}")


def _flatten_to_opaque_white(png_path: str) -> None:
    """
    pdftocairo's PNG output leaves non-inked areas fully transparent (alpha=0).
    That looks fine composited over a light chat background, but Chainlit's
    image lightbox/zoom view uses a dark backdrop, so the near-black ink shows
    up on a near-black background and the diagram is effectively invisible
    when enlarged. Composite onto solid white so the PNG is fully opaque.
    """
    from PIL import Image

    im = Image.open(png_path)
    if im.mode not in ("RGBA", "LA") and not (im.mode == "P" and "transparency" in im.info):
        return

    im = im.convert("RGBA")
    background = Image.new("RGBA", im.size, (255, 255, 255, 255))
    background.paste(im, mask=im.split()[-1])
    background.convert("RGB").save(png_path, "PNG")


def pdf_to_png(pdf_path: str, png_path: str, dpi: int = 300) -> None:
    # Prefer pdftocairo if available
    try:
        run_cmd([
            "pdftocairo",
            "-png",
            "-singlefile",
            "-r", str(dpi),
            pdf_path,
            os.path.splitext(png_path)[0],
        ])
        produced = os.path.splitext(png_path)[0] + ".png"
        if produced != png_path:
            os.replace(produced, png_path)
        _flatten_to_opaque_white(png_path)
        return
    except Exception:
        pass

    # Fallback to ImageMagick (magick)
    try:
        run_cmd([
            "magick",
            "-density", str(dpi),
            pdf_path + "[0]",
            "-quality", "100",
            png_path
        ])
        _flatten_to_opaque_white(png_path)
        return
    except Exception as e:
        raise RuntimeError(
            "Could not convert PDF to PNG. Install poppler (pdftocairo) or ImageMagick (magick).\n"
            f"Last error: {e}"
        )

TEXT_TO_PYTHON = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
}

def evaluate_expression(expression: str) -> float:
    """
    Evaluates string expressions into proper numbers using the TEXT_TO_PYTHON dictionary
    """
    return float(eval(expression, {"__builtins__": {}}, TEXT_TO_PYTHON))


import sympy
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations, implicit_multiplication_application, convert_xor,
)

_LABEL_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)
_LABEL_LOCALS = {"pi": sympy.pi, "e": sympy.E}

def _split_top_level_fraction(text: str):
    """Splits on the first '/' outside any parens, e.g. "(x+1)/2" -> ("(x+1)", "2")."""
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "/" and depth == 0:
            return text[:i], text[i + 1:]
    return None


def _parse(text: str):
    return parse_expr(text, transformations=_LABEL_TRANSFORMATIONS, local_dict=_LABEL_LOCALS)


def label_to_latex(raw: str) -> str:
    """
    Converts a plain-text edge label expression into LaTeX math, e.g.
    "25/2" -> \\frac{25}{2}, "4*sqrt(3)" -> 4\\sqrt{3}, "x^2" -> x^{2}.
    Uses the same Python-style expression syntax as the rest of the topology
    (sqrt(3), not sqrt3) for consistency.
    """
    try:
        # Fractions are split and rendered as \frac{num}{den} directly rather
        # than parsed as a division by sympy, since sympy otherwise either
        # distributes it (e.g. (x+1)/2 -> x/2 + 1/2) or, without auto-simplify,
        # leaves a redundant "1 * ..." factor on plain numeric fractions.
        split = _split_top_level_fraction(raw)
        if split:
            numerator, denominator = split
            return f"\\frac{{{sympy.latex(_parse(numerator))}}}{{{sympy.latex(_parse(denominator))}}}"
        return sympy.latex(_parse(raw))
    except Exception as e:
        raise ValueError(f"Edge label '{raw}' is not a valid expression: {e}")


_VERTEX_KEY_RE = re.compile(r"^\s*Vertex\s+([A-Z])")
_EDGE_KEY_RE = re.compile(r"^\s*Edge\s+([A-Z])\s*-\s*([A-Z])")
_ANGLE_KEY_RE = re.compile(r"^\s*Angle\s+([A-Z]{3})")
_ARC_KEY_RE = re.compile(r"^\s*Arc\s+([A-Z]{3})")
_CIRCLE_KEY_RE = re.compile(r"^\s*Circle\s+([A-Z])")


def topology_line_key(line: str) -> str:
    """
    Returns the canonical "slot" a topology line occupies, so an edit can
    replace a line (e.g. a moved vertex, a changed angle measure) instead
    of duplicating it. Lines with no recognized keyed prefix -- including
    Shaded Region lines, which have no natural short key -- use their own
    exact text as the key, so they can only be replaced/removed by exact
    match.
    """
    line = line.strip()
    if m := _VERTEX_KEY_RE.match(line):
        return f"Vertex {m.group(1)}"
    if m := _EDGE_KEY_RE.match(line):
        # Unlike Angle/Arc, an edge has no direction -- A-B and B-A are the
        # same segment, so they must resolve to the same key.
        a, b = sorted((m.group(1), m.group(2)))
        return f"Edge {a}-{b}"
    if m := _ANGLE_KEY_RE.match(line):
        return f"Angle {m.group(1)}"
    if m := _ARC_KEY_RE.match(line):
        return f"Arc {m.group(1)}"
    if m := _CIRCLE_KEY_RE.match(line):
        return f"Circle {m.group(1)}"
    return line


def apply_topology_edit(current_topology: str, add_lines, remove_keys) -> str:
    """
    Applies an incremental edit to a topology instead of requiring it to be
    retyped in full. `add_lines` are inserted, replacing any existing line
    with the same key (see topology_line_key) rather than duplicating it.
    `remove_keys` delete the line with that key (or, for unkeyed lines like
    Shaded Region, the exact line text). Returns the merged topology text.
    """
    ordered_keys = []
    by_key = {}
    for line in current_topology.splitlines():
        if not line.strip():
            continue
        key = topology_line_key(line)
        if key not in by_key:
            ordered_keys.append(key)
        by_key[key] = line.strip()

    for raw_key in remove_keys or []:
        key = raw_key.strip()
        if key in by_key:
            del by_key[key]
            ordered_keys.remove(key)

    for line in add_lines or []:
        if not line.strip():
            continue
        key = topology_line_key(line)
        if key not in by_key:
            ordered_keys.append(key)
        by_key[key] = line.strip()

    return "\n".join(by_key[k] for k in ordered_keys)
