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

    #Dictionary containing all vertices of the graph
    vertices = {}

    #Regex looking for a substring of the format "Vertex [Label]:([x coordinate],[y coordinate])" with optional whitespace
    vertices_regex = re.compile(r"Vertex\s*([A-Z])\s*\:\s*\(([^,]+)\s*,\s*(.+)\s*\)", re.IGNORECASE)

    for match in vertices_regex.finditer(topology):
        name = match.group(1).upper()
        x = evaluate_expression(match.group(2).strip())
        y = evaluate_expression(match.group(3).strip())
        vertices.update({name : point((x, y), "above right")})

    #List containing all edges of the graph
    edges = []

    #Regex looking for a substring of the format "Segment [Endpoint 1]-[Endpoint 2] with optional whitespace
    edges_regex = re.compile(r"Segment\s*([A-Z])\s*\-\s*([A-Z])", re.IGNORECASE)

    for match in edges_regex.finditer(topology):
        endpoint1 = match.group(1)
        endpoint2 = match.group(2)
        edges.append([endpoint1, endpoint2])

    #List containing all edges of the graph
    circles = []

    #Regex looking for a substring of the format "Circle [Label] Center [Center Point] Radius [Radius] with optional whitespace
    circles_regex = re.compile(r"Circle\s*([A-Z])\s*Center\s*([A-Z])\s*Radius(.+)", re.IGNORECASE)

    for match in circles_regex.finditer(topology):
        label = match.group(1)
        center = match.group(2)
        radius = evaluate_expression(match.group(3).strip())
        circles.append([center, radius])

    drawingInfo = {
        "vertices" : vertices,
        "edges" : edges,
        "circles" : circles,
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

        for edge in edges:
            point1 = vertexCoordinates.get(edge[0])
            if (point1 is None):
                continue
            point2 = vertexCoordinates.get(edge[1])
            if (point2 is None):
                continue
            pic.append(
                TikZDraw(
                    [point1, "--", point2]
                )
            )
        
        for circle in circles:
            center = circle[0]
            if (center is None):
                continue
            centerCoordinates = vertexCoordinates.get(center)
            if (centerCoordinates is None):
                continue
            radius = circle[1]
            if (radius is None):
                continue
            pic.append(
                TikZDraw(
                    [centerCoordinates, "circle"],
                    options = TikZOptions(radius = radius)
                )
            )
    
    doc.generate_pdf("tikzdraw", clean_tex = False)

    pdf_to_png("tikzdraw.pdf", "tikzdraw.png", dpi = dpi)
    pngpath = Path() / "tikzdraw.png"
    return pngpath.read_bytes()