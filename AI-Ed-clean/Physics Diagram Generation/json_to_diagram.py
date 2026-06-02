# Updated FBD renderer
# The renderer auto-computes bounds from the **actual drawn segments** so diagrams
# stay nicely scaled.

import math
from typing import Dict, Any, Tuple, Optional, List
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.transforms import Affine2D


def _compute_arrow_from_angle(start: Tuple[float, float], angle_deg: float, length: float) -> Tuple[float, float]:
    theta = math.radians(angle_deg)
    dx = length * math.cos(theta)
    dy = length * math.sin(theta)
    return start[0] + dx, start[1] + dy


def _points_from_surfaces(data: Dict[str, Any], default_length: float = 6.0) -> List[Tuple[float, float]]:
    """Return points that will be rendered for surfaces, honoring 'length'."""
    pts: List[Tuple[float, float]] = []

    # Heuristic center if not explicitly provided
    def_body = (0.0, 0.0)
    if data.get("bodies"):
        b0 = data["bodies"][0]
        def_body = (b0.get("position", {}).get("x", 0.0), b0.get("position", {}).get("y", 0.0))

    for s in data.get("surfaces", []):
        st = s.get("type", "horizontal")
        length = float(s.get("length", default_length))
        half = length / 2.0

        if st in ("horizontal", "ground"):
            y = s.get("y", 0.0)
            cx = s.get("center", {}).get("x", def_body[0])
            pts.append((cx - half, y))
            pts.append((cx + half, y))

        elif st == "incline":
            angle = math.radians(s.get("angle_deg", 0.0))
            if "through" in s:
                x0, y0 = s["through"]["x"], s["through"]["y"]
            else:
                x0, y0 = def_body
            # direction unit vector along incline
            ux, uy = math.cos(angle), math.sin(angle)
            p1 = (x0 - half * ux, y0 - half * uy)
            p2 = (x0 + half * ux, y0 + half * uy)
            pts.extend([p1, p2])

    return pts


def _collect_extents(data: Dict[str, Any]) -> Tuple[float, float, float, float]:
    xs, ys = [], []

    # Bodies
    for b in data.get("bodies", []):
        cx, cy = b.get("position", {}).get("x", 0.0), b.get("position", {}).get("y", 0.0)
        w, h = b.get("size", {}).get("width", 1.0), b.get("size", {}).get("height", 1.0)
        xs += [cx - w / 2, cx + w / 2]
        ys += [cy - h / 2, cy + h / 2]

    # Forces
    for f in data.get("forces", []):
        arrow = f.get("arrow", {})
        if "start" in arrow:
            xs.append(arrow["start"]["x"]); ys.append(arrow["start"]["y"])
        if "end" in arrow:
            xs.append(arrow["end"]["x"]); ys.append(arrow["end"]["y"])
        elif "angle_deg" in arrow and "start" in arrow:
            x1, y1 = _compute_arrow_from_angle(
                (arrow["start"]["x"], arrow["start"]["y"]),
                arrow.get("angle_deg", 0.0),
                arrow.get("length", 1.0))
            xs.append(x1); ys.append(y1)

    # Surfaces (finite size)
    for (x, y) in _points_from_surfaces(data):
        xs.append(x); ys.append(y)

    if not xs:
        return -2, 2, -2, 2

    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    pad_x = max(0.5, 0.1 * (xmax - xmin + 1e-6))
    pad_y = max(0.5, 0.1 * (ymax - ymin + 1e-6))
    return xmin - pad_x, xmax + pad_x, ymin - pad_y, ymax + pad_y


def render_fbd_sized_surfaces(data: Dict[str, Any],
                              out_svg: str = "data/fbd.svg",
                              out_png: Optional[str] = "data/fbd.png") -> Tuple[str, Optional[str]]:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_aspect("equal")
    ax.axis("off")

    # Compute limits *including* finite surfaces
    xmin, xmax, ymin, ymax = _collect_extents(data)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    # Draw finite-length surfaces
    for s in data.get("surfaces", []):
        st = s.get("type", "horizontal")
        length = float(s.get("length", 6.0))
        half = length / 2.0

        if st in ("horizontal", "ground"):
            y = s.get("y", 0.0)
            cx = s.get("center", {}).get("x", 0.0)
            ax.plot([cx - half, cx + half], [y, y], linewidth=2)

        elif st == "incline":
            angle = math.radians(s.get("angle_deg", 0.0))
            if "through" in s:
                x0, y0 = s["through"]["x"], s["through"]["y"]
            else:
                x0, y0 = 0.0, 0.0
            ux, uy = math.cos(angle), math.sin(angle)
            p1 = (x0 - half * ux, y0 - half * uy)
            p2 = (x0 + half * ux, y0 + half * uy)
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], linewidth=2)

    # Bodies
    body_centers = {}
    for b in data.get("bodies", []):
        bid = b.get("id", "body")
        cx, cy = b.get("position", {}).get("x", 0.0), b.get("position", {}).get("y", 0.0)
        w,  h  = b.get("size", {}).get("width", 1.0), b.get("size", {}).get("height", 1.0)
        rot = b.get("rotation_deg", 0.0)

        # Draw rectangle, then rotate ABOUT ITS CENTER
        rect = Rectangle((cx - w/2, cy - h/2), w, h, angle=0, fill=False, linewidth=2)
        rect.set_transform(Affine2D().rotate_deg_around(cx, cy, rot) + ax.transData)
        ax.add_patch(rect)

        body_centers[bid] = (cx, cy)

        # Upright, centered label
        if "label" in b:
            ax.text(cx, cy, b["label"], ha="center", va="center", rotation=0)

    # Forces (arrows)
    for f in data.get("forces", []):
        arrow = f.get("arrow", {})
        if "start" in arrow:
            x0, y0 = arrow["start"]["x"], arrow["start"]["y"]
        else:
            x0, y0 = body_centers.get(f.get("on"), (0.0, 0.0))

        if "end" in arrow:
            x1, y1 = arrow["end"]["x"], arrow["end"]["y"]
        else:
            angle_deg = arrow.get("angle_deg", 270.0)
            length = arrow.get("length", 1.0)
            x1, y1 = _compute_arrow_from_angle((x0, y0), angle_deg, length)

        ap = FancyArrowPatch((x0, y0), (x1, y1), arrowstyle='-|>', mutation_scale=15, linewidth=2, shrinkA=0, shrinkB=0, color="Blue")
        ax.add_patch(ap)

        lbl = f.get("label", {})
        if "text" in lbl:
            dx = lbl.get("offset", {}).get("dx", 0.0)
            dy = lbl.get("offset", {}).get("dy", 0.0)
            ax.text(x1 + dx, y1 + dy, lbl["text"], ha="center", va="center")

    # Axes
    labels_cfg = data.get("labels", {})
    if labels_cfg.get("show_axes", False):
        ox, oy = labels_cfg.get("origin", {}).get("x", 0.0), labels_cfg.get("origin", {}).get("y", 0.0)
        ax.arrow(ox, oy, 1.0, 0.0, length_includes_head=True, head_width=0.05, head_length=0.1, linewidth=1)
        ax.arrow(ox, oy, 0.0, 1.0, length_includes_head=True, head_width=0.05, head_length=0.1, linewidth=1)
        ax.text(ox + 1.1, oy, 'x', va='center')
        ax.text(ox, oy + 1.1, 'y', ha='center')

    fig.savefig(out_svg, bbox_inches="tight")
    if out_png:
        fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_svg, out_png


# ---------- Example usage with finite surfaces ----------
# You are a diagram JSON generator. Output ONLY JSON matching the schema.\n\nProblem:\n
# A block of mass m rests on a 30° incline. Draw a free body diagram with W, N, and friction f.
if False:
    example = {
        "bodies": [
            {"id": "block1", "type": "block", "position": {"x": 0, "y": 0}, "size": {"width": 0.6, "height": 0.4}, "rotation_deg": 30, "label": ""}
        ],
        "surfaces": [
            {"id": "incline", "type": "incline", "angle_deg": 30, "through": {"x": -0.4, "y": -0.5}, "length": 5.0},
        ],
        "forces": [
            {"id": "W", "type": "weight", "on": "block1",
             "arrow": {"start": {"x": 0.0, "y": 0.0}, "angle_deg": 270, "length": 1.1},
             "label": {"text": "W", "offset": {"dx": 0.0, "dy": 0.0}}},
            {"id": "N", "type": "normal", "on": "block1",
             "arrow": {"start": {"x": 0.0, "y": 0.0}, "angle_deg": 120, "length": 0.9},
             "label": {"text": "N", "offset": {"dx": 0.0, "dy": 0.0}}},
            {"id": "f", "type": "friction", "on": "block1",
             "arrow": {"start": {"x": 0.0, "y": 0.0}, "angle_deg": 30, "length": 0.8},
             "label": {"text": "f", "offset": {"dx": 0.0, "dy": 0.0}}}
        ],
        "labels": {"show_axes": True, "origin": {"x": 1.0, "y": -2.0}}
    }

example = {}







"""
{
    "bodies": [
        {"id": "block1", "type": "block", "position": {"x":0.0,"y":0.5}, "size": {"width":0.6, "height":0.4}, "rotation_deg":30, "label":""}
    ],
    "surfaces": [
        {"incline","incline","angle_deg":3270,"through":{"x":-0.4,"y":-0.5
        ],
    "forces":[],
    "labels":{show_axes":true,"origin":{"x":1.0,"dy":0.9}}
}
#"""








"""
{
    "bodies": [
        {"id": "block1", "type": "block", "position":{"x":0.0,"y":0.5}, "size":{"width":0.6,"height":0.4}, "rotation_deg":30,"label":""}
    ],
    "surfaces": [
        {" id": "incline", "type": "inclinecline", "angle_deg":35, "through":{"x":-0.4,"y":-0.7}, "length":5.0}
    ],
    "forces": [
        {"_id": "W", "type": "weight", "on": "block1arrow":{"start":{"x":5.4," y":0.7}}},
        {"id", "N", "type": "normal", "on": "N", "block1",
         "arrow":{"start}, {"x":00,"y":-2.0}}},
        {'id": "f", "type": "friction", "on":
         "arrow": {"start": "N", "angle_deg': 270, "length": 1.1},
         "label": {"text":"f", "offset": {"dx":0.8, "dy":0.9}}}
    ],
    "labels": {"show_axes": true, "origin": {"x":1.0," y":-2.7}}
}
#"""

"""
{
    "bodies": [
        {"id": "block1", "type": "block", "position":{"x":0.0,"y":0.5}, "size":{"width":0.6,"height":0.4}, "rotation_deg":30,"label":""}
    ],
    "surfaces": [
        {" id": "incline", "type": "inclinecline", "angle_deg":35, "through":{"x":-0.4,"y":-0.7}, "length":5.0}
    ],
    "forces": [
        {"_id": "W", "type": "weight", "on": "block1arrow":{"start":{"x":5.4," y":0.7}}},
        {"id": "N", "type": "normal", "on": "N", "block1":{},
         "arrow":{"start"}, {"x":0,"y":-2.0}},
        {"id": "f", "type": "friction", "on":"",
         "arrow": {"start": "N", "angle_deg": 270, "length": 1.1},
         "label": {"text":"f", "offset": {"dx":0.8, "dy":0.9}}}
    ],
    "labels": {"show_axes": true, "origin": {"x":1.0, " y":-2.7}}
}
#"""

svg_path, png_path = render_fbd_sized_surfaces(example)
(svg_path, png_path)
