import subprocess
import os
import math
import re

def run_cmd(cmd: list[str], cwd=None) -> None:
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n  {' '.join(cmd)}\n\nOutput:\n{p.stdout}")

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


_VERTEX_KEY_RE = re.compile(r"^\s*Vertex\s+([A-Z])")
_SEGMENT_KEY_RE = re.compile(r"^\s*Segment\s+([A-Z])\s*-\s*([A-Z])")
_ANGLE_KEY_RE = re.compile(r"^\s*Angle\s+([A-Z]{3})")
_ARC_KEY_RE = re.compile(r"^\s*Arc\s+([A-Z]{3})")
_CIRCLE_KEY_RE = re.compile(r"^\s*Circle\s+([A-Z])")


def topology_line_key(line: str) -> str:
    """
    Returns the canonical "slot" a topology line occupies, so an edit can
    replace a line (e.g. a moved vertex, a changed angle measure) instead
    of duplicating it. Lines with no recognized keyed prefix -- including
    Shade lines, which have no natural short key -- use their own exact
    text as the key, so they can only be replaced/removed by exact match.
    """
    line = line.strip()
    if m := _VERTEX_KEY_RE.match(line):
        return f"Vertex {m.group(1)}"
    if m := _SEGMENT_KEY_RE.match(line):
        return f"Segment {m.group(1)}-{m.group(2)}"
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
    Shade, the exact line text). Returns the merged topology text.
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
