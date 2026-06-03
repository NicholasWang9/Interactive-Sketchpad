import argparse
import os
import random
import math
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path

class point:

    #Coordinates of the point's location
    coordinates: Tuple[float, float]
    #Planned location of the label
    label_position: str

    def __init__(self, coordinates, label_position = None):
        self.coordinates = coordinates
        self.label_position = label_position

def run_cmd(cmd: List[str], cwd=None) -> None:
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

def parse_topology_to_dict(topology: str) -> dict:

    print(f"parsing ({topology})")

    #Dictionary containing all vertices of the graph
    vertices = {}

    #Regex looking for a substring of the format "Vertex [Label]:([x coordinate],[y coordinate])" with optional whitespace
    vertices_regex = re.compile(r"Vertex\s*([A-Z])\s*\:\s*\(([^,]+)\s*,\s*(.+)\s*\)", re.IGNORECASE)

    for match in vertices_regex.finditer(topology):
        print(f"Found match: {match.group()} at position {match.start()} to {match.end()}")
        name = match.group(1).upper()
        x = evaluate_expression(match.group(2).strip())
        y = evaluate_expression(match.group(3).strip())
        vertices.update({name : point((x, y), "above right")})

    drawingInfo = {
        "vertices" : vertices
    }

    return drawingInfo

from pylatex import (
    Document,
    TikZ,
    TikZCoordinate,
    TikZDraw,
    TikZNode,
    TikZPath,
    TikZOptions,
    TikZUserPath,
    Command
)

def generate(topology: str, *, dpi: int = 300, pretty: bool = True) -> bytes:
    print("calling generate")

    doc = Document()

    drawingInfo = parse_topology_to_dict(topology)

    doc.preamble.append(Command('pagestyle', 'empty'))

    vertices = drawingInfo.get("vertices")
    edges = drawingInfo.get("edges")
    circles = drawingInfo.get("circles")
    arcs = drawingInfo.get("arcs")

    vertexCoordinates = dict()

    with doc.create(TikZ()) as pic:

        for vertexName in vertices.keys():
            point = vertices.get(vertexName)
            vertex = point.coordinates
            coordinate = TikZCoordinate(vertex[0], vertex[1])
            vertexCoordinates.update({vertexName : coordinate})
            #If the label_position is None then the point should not be labeled and the node is unnecessary
            if (point.label_position is not None):
                node = TikZNode(
                    handle = vertexName,
                    at = coordinate,
                    text = vertexName,
                    options = TikZOptions(point.label_position)
                )
                pic.append(node)
                pic.append(
                    TikZDraw(
                        [coordinate, "circle"],
                        options = TikZOptions(fill = "black", radius = 0.02)
                    )
                )
    
    doc.generate_pdf("tikzdraw", clean_tex = False)

    pdf_to_png("tikzdraw.pdf", "tikzdraw.png", dpi = dpi)
    pngpath = Path() / "tikzdraw.png"
    return pngpath.read_bytes()