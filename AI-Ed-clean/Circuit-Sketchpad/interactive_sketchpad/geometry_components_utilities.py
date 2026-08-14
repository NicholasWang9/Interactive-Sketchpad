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
        return f"Edge {m.group(1)}-{m.group(2)}"
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


def reconcile_full_regeneration(old_topology: str, new_topology: str) -> str:
    """
    Guards against drift when `generate_geometry` (full topology) is called
    again after a working diagram already exists. Re-deriving every
    coordinate from scratch is a common source of a previously-placed point
    silently shifting, or the whole diagram ending up flipped or rotated,
    even when nothing was actually supposed to change. So: for any line
    whose key (see topology_line_key) already existed, the OLD line wins --
    the freshly generated version of it is discarded. Only genuinely new
    keys from `new_topology` are taken. Lines from `old_topology` that the
    regeneration dropped (e.g. the model forgot to retype them) are kept
    rather than silently lost.

    This makes `edit_geometry` the only way to intentionally move, change,
    or remove an existing object -- a plain `generate_geometry` call can no
    longer do that once a working diagram exists.
    """
    old_by_key = {}
    old_order = []
    for line in old_topology.splitlines():
        if not line.strip():
            continue
        key = topology_line_key(line)
        if key not in old_by_key:
            old_order.append(key)
        old_by_key[key] = line.strip()

    merged_order = []
    merged_by_key = {}
    seen_keys = set()
    for line in new_topology.splitlines():
        if not line.strip():
            continue
        key = topology_line_key(line)
        seen_keys.add(key)
        if key not in merged_by_key:
            merged_order.append(key)
        merged_by_key[key] = old_by_key.get(key, line.strip())

    for key in old_order:
        if key not in seen_keys:
            merged_order.append(key)
            merged_by_key[key] = old_by_key[key]

    return "\n".join(merged_by_key[k] for k in merged_order)
