import argparse
import os
import random
import numpy as np
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

    #Regex looking for a substring of the format "Vertex [Label]:([x coordinate],[y coordinate]) above left" with optional whitespace
    vertices_regex = re.compile(
        r"Vertex\s*([A-Z])\s*:\s*\(\s*([^,]+)\s*,\s*((?:[^()]|\([^()]*\))+)\s*\)\s*(above left|above right|below left|below right|above|below|left|right)?",
        re.IGNORECASE,
    )
    # Nick this was your old one:
    # vertices_regex = re.compile(
    #     r"Vertex\s*([A-Z])\s*\:\s*\(([^,]+)\s*,\s*(.+)\s*\)", re.IGNORECASE)


    for match in vertices_regex.finditer(topology):
        name = match.group(1).upper()
        x = evaluate_expression(match.group(2).strip())
        y = evaluate_expression(match.group(3).strip())
        label_position = match.group(4)

        if label_position is None:
            label_position = "above right"
        else:
            label_position = label_position.lower()

        vertices.update({name : point((x, y), label_position)})

    #List containing all edges of the graph
    edges = []

    #Regex looking for a substring of the format "Segment [Endpoint 1]-[Endpoint 2]" with optional whitespace
    edges_regex = re.compile(r"Segment\s*([A-Z])\s*\-\s*([A-Z])", re.IGNORECASE)

    for match in edges_regex.finditer(topology):
        endpoint1 = match.group(1)
        endpoint2 = match.group(2)
        edges.append([endpoint1, endpoint2])

    #List containing all circles of the graph
    circles = []

    #Regex looking for a substring of the format "Circle [Label] Center [Center Point] Radius [Radius] with optional whitespace
    circles_regex = re.compile(r"Circle\s*([A-Z])\s*Center\s*([A-Z])\s*Radius(.+)", re.IGNORECASE)

    for match in circles_regex.finditer(topology):
        label = match.group(1)
        center = match.group(2)
        radius = evaluate_expression(match.group(3).strip())
        circles.append([center, radius])

    #List containing all angles of the graph, BRYAN ADDED NICK PLS CHECK
    angles = []

    #Regex looking for substrings like:
    #Angle CBD=130
    #Angle BDE=x
    #Angle XYZ=45-y
    angles_regex = re.compile(
        r"angle\s+([A-Z]{3})\s*=\s*([A-Za-z0-9_+\-*/().]+)",
        re.IGNORECASE,
    )

    for match in angles_regex.finditer(topology):
        angle_name = match.group(1).upper()
        raw_value = match.group(2).strip()

        start_name = angle_name[0]
        vertex_name = angle_name[1]
        end_name = angle_name[2]

        if re.search(r"[A-Za-z_]", raw_value):
            angle_value = raw_value
        else:
            angle_value = evaluate_expression(raw_value)

        angles.append([start_name, vertex_name, end_name, angle_value])

    #List containing all arcs of the graph
    arcs = []

    #Regex looking for substrings like:
    #Arc AOC
    #Arc BOD
    #Arc XOY
    #
    #Arc AOC means:
    #A is the start point
    #O is the center
    #C is the end point
    #The arc is drawn clockwise from A to C around O
    arcs_regex = re.compile(r"Arc\s+([A-Z]{3})", re.IGNORECASE)

    for match in arcs_regex.finditer(topology):
        arc_name = match.group(1).upper()

        start_name = arc_name[0]
        center_name = arc_name[1]
        end_name = arc_name[2]

        arcs.append([start_name, center_name, end_name])

    drawingInfo = {
        "vertices" : vertices,
        "edges" : edges,
        "circles" : circles,
        "angles" : angles,
        "arcs" : arcs,
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

    doc.preamble.append(Command('usepackage', 'geometry'))
    doc.preamble.append(Command('geometry', 'margin = 0.1in'))

    vertices = drawingInfo.get("vertices")
    edges = drawingInfo.get("edges")
    circles = drawingInfo.get("circles")
    angles = drawingInfo.get("angles")
    arcs = drawingInfo.get("arcs")

    min_x = 0
    max_x = 0
    min_y = 0
    max_y = 0

    vertexCoordinates = dict()

    rawVertexCoordinates = np.array([vertex.coordinates for vertex in vertices.values() if vertex.label_position is not None])

    if vertices is not None:
        for vertexName in vertices.keys():
            point = vertices.get(vertexName)
            vertex = point.coordinates
            coordinate = TikZCoordinate(vertex[0], vertex[1])
            vertexCoordinates.update({vertexName : coordinate})
            min_x = min(rawVertexCoordinates[:, 0])
            max_x = max(rawVertexCoordinates[:, 0])
            min_y = min(rawVertexCoordinates[:, 1])
            max_y = max(rawVertexCoordinates[:, 1])

    if circles is not None:
        for circle in circles:
            center = vertices.get(circle[0]).coordinates
            radius = circle[1]
            min_x = min(min_x, center[0] - radius)
            max_x = max(max_x, center[0] + radius)
            min_y = min(min_y, center[1] - radius)
            max_y = max(max_y, center[1] + radius)

    #BRYAN ADDED NICK PLS CHECK
    if angles is not None:
        for angle in angles:
            start_name = angle[0]
            vertex_name = angle[1]
            end_name = angle[2]

            start_point = vertices.get(start_name)
            vertex_point = vertices.get(vertex_name)
            end_point = vertices.get(end_name)

            if start_point is None or vertex_point is None or end_point is None:
                continue

            start = start_point.coordinates
            vertex = vertex_point.coordinates
            end = end_point.coordinates

            # Angles are drawn near the vertex.
            # This padding gives the angle marker and label some room.
            padding = 0.5

            min_x = min(min_x, start[0], vertex[0] - padding, end[0])
            max_x = max(max_x, start[0], vertex[0] + padding, end[0])
            min_y = min(min_y, start[1], vertex[1] - padding, end[1])
            max_y = max(max_y, start[1], vertex[1] + padding, end[1])
    
    if arcs is not None:
        for arc in arcs:
            start_name = arc[0]
            center_name = arc[1]
            end_name = arc[2]

            start_point = vertices.get(start_name)
            center_point = vertices.get(center_name)
            end_point = vertices.get(end_name)

            if start_point is None or center_point is None or end_point is None:
                continue

            start = start_point.coordinates
            center = center_point.coordinates

            radius = math.dist(center, start)

            # center = vertices.get(arc.center).coordinates
            # radius = arc.radius
            min_x = min(min_x, center[0] - radius)
            max_x = max(max_x, center[0] + radius)
            min_y = min(min_y, center[1] - radius)
            max_y = max(max_y, center[1] + radius)

    x_width = max_x - min_x
    y_width = max_y - min_y
    max_width = max(x_width, y_width)
    scale_factor = 20 / max_width

    vertexCoordinates = dict()

    with doc.create(TikZ()) as pic:

        for vertexName in vertices.keys():
            point = vertices.get(vertexName)
            vertex = [coordinate * scale_factor for coordinate in point.coordinates]
            coordinate = TikZCoordinate(vertex[0], vertex[1])
            vertexCoordinates.update({vertexName : coordinate})
            #If the label_position is None then the point should not be labeled and the node is unnecessary
            if (point.label_position is not None):
                node = TikZNode(
                    handle = vertexName,
                    at = coordinate,
                    text = vertexName,
                    options = TikZOptions(point.label_position, "font=\\large")
                )
                pic.append(node)
                pic.append(
                    TikZDraw(
                        [coordinate, "circle"],
                        options = TikZOptions(fill = "black", radius = 0.04, )
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
                    [point1, "--", point2],
                    options = TikZOptions("line width = 1pt")
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
                    options = TikZOptions("line width = 1pt", radius = radius * scale_factor)
                )
            )
        
        #BRYAN ADDED NICK PLS CHECK bro there's so much 
        for angle in angles:
            start_name = angle[0]
            vertex_name = angle[1]
            end_name = angle[2]
            angle_value = angle[3]

            start_point = vertices.get(start_name)
            vertex_point = vertices.get(vertex_name)
            end_point = vertices.get(end_name)

            if start_point is None or vertex_point is None or end_point is None:
                continue

            start = [coordinate * scale_factor for coordinate in start_point.coordinates]
            vertex = [coordinate * scale_factor for coordinate in vertex_point.coordinates]
            end = [coordinate * scale_factor for coordinate in end_point.coordinates]

            start_angle = math.degrees(
                math.atan2(start[1] - vertex[1], start[0] - vertex[0])
            )

            end_angle = math.degrees(
                math.atan2(end[1] - vertex[1], end[0] - vertex[0])
            )

            ccw_angle = (end_angle - start_angle) % 360

            if isinstance(angle_value, float) or isinstance(angle_value, int):
                clockwise_angle = 360 - ccw_angle

                if abs(ccw_angle - angle_value) <= abs(clockwise_angle - angle_value):
                    final_end_angle = start_angle + ccw_angle
                else:
                    final_end_angle = start_angle - clockwise_angle
            else:
                if ccw_angle <= 180:
                    final_end_angle = start_angle + ccw_angle
                else:
                    final_end_angle = start_angle - (360 - ccw_angle)

            length1 = math.dist(vertex, start)
            length2 = math.dist(vertex, end)

            marker_size = min(length1, length2) * 0.10
            marker_size = max(0.15, min(marker_size, 0.45))

            #Right angle marker
            if angle_value == 90:
                dx1 = start[0] - vertex[0]
                dy1 = start[1] - vertex[1]
                dx2 = end[0] - vertex[0]
                dy2 = end[1] - vertex[1]

                length1 = math.hypot(dx1, dy1)
                length2 = math.hypot(dx2, dy2)

                if length1 == 0 or length2 == 0:
                    continue

                u1 = [dx1 / length1, dy1 / length1]
                u2 = [dx2 / length2, dy2 / length2]

                square_size = marker_size * 0.8

                a = TikZCoordinate(
                    vertex[0] + square_size * u1[0],
                    vertex[1] + square_size * u1[1]
                )

                b = TikZCoordinate(
                    vertex[0] + square_size * u1[0] + square_size * u2[0],
                    vertex[1] + square_size * u1[1] + square_size * u2[1]
                )

                c = TikZCoordinate(
                    vertex[0] + square_size * u2[0],
                    vertex[1] + square_size * u2[1]
                )

                pic.append(
                    TikZDraw(
                        [a, "--", b, "--", c],
                        options = TikZOptions("line width = 0.8pt")
                    )
                )

                label_coordinate = TikZCoordinate(
                    vertex[0] + 1.2 * square_size * (u1[0] + u2[0]),
                    vertex[1] + 1.2 * square_size * (u1[1] + u2[1])
                )

                # Don't need to label right angles
                # label_node = TikZNode(
                #     at = label_coordinate,
                #     text = "$90^\\circ$"
                # )

                # pic.append(label_node)

            #Regular angle marker
            else:
                arc_start_x = vertex[0] + marker_size * math.cos(math.radians(start_angle))
                arc_start_y = vertex[1] + marker_size * math.sin(math.radians(start_angle))

                arc_start = TikZCoordinate(arc_start_x, arc_start_y)

                pic.append(
                    TikZDraw(
                        [
                            arc_start,
                            TikZUserPath(
                                f"arc[start angle = {start_angle}, end angle = {final_end_angle}, radius = {marker_size}]"
                            )
                        ],
                        options = TikZOptions("line width = 0.8pt")
                    )
                )

                mid_angle = (start_angle + final_end_angle) / 2
                label_radius = marker_size + 0.35

                label_coordinate = TikZCoordinate(
                    vertex[0] + label_radius * math.cos(math.radians(mid_angle)),
                    vertex[1] + label_radius * math.sin(math.radians(mid_angle))
                )

                if isinstance(angle_value, float) or isinstance(angle_value, int):
                    label_text = f"${angle_value:g}^\\circ$"
                else:
                    label_text = f"${angle_value}$"

                label_node = TikZNode(
                    at = label_coordinate,
                    text = label_text,
                    options = TikZOptions("font=\\normalsize")
                )

                pic.append(label_node)

        #Arc stuff
        for arc in arcs:
            start_name = arc[0]
            center_name = arc[1]
            end_name = arc[2]

            startCoordinates = vertexCoordinates.get(start_name)
            centerCoordinates = vertexCoordinates.get(center_name)
            endCoordinates = vertexCoordinates.get(end_name)

            if startCoordinates is None or centerCoordinates is None or endCoordinates is None:
                continue

            start_point = vertices.get(start_name)
            center_point = vertices.get(center_name)
            end_point = vertices.get(end_name)

            if start_point is None or center_point is None or end_point is None:
                continue

            start = [coordinate * scale_factor for coordinate in start_point.coordinates]
            center = [coordinate * scale_factor for coordinate in center_point.coordinates]
            end = [coordinate * scale_factor for coordinate in end_point.coordinates]

            radius = math.dist(center, start)

            if radius == 0:
                continue

            start_angle = math.degrees(
                math.atan2(start[1] - center[1], start[0] - center[0])
            )

            end_angle = math.degrees(
                math.atan2(end[1] - center[1], end[0] - center[0])
            )

            #Arc ABC means:
            #A is the start point
            #B is the center
            #C is the end point
            #Draw clockwise from A to C
            ccw_delta = (end_angle - start_angle) % 360

            if ccw_delta == 0:
                clockwise_delta = -360
            else:
                clockwise_delta = ccw_delta - 360

            pic.append(
                TikZDraw(
                    [
                        startCoordinates,
                        TikZUserPath(
                            f"arc[start angle = {start_angle}, delta angle = {clockwise_delta}, radius = {radius}]"
                        )
                    ],
                    options = TikZOptions("line width = 1pt")
                )
            )
    
    doc.generate_pdf("tikzdraw", clean_tex = False)

    pdf_to_png("tikzdraw.pdf", "tikzdraw.png", dpi = dpi)
    pngpath = Path() / "tikzdraw.png"
    return pngpath.read_bytes()
