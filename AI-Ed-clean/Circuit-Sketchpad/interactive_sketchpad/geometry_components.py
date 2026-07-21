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

class arc:

    #Label of the point at the arc's center
    center: str
    #Label of a point on the counterclockwise edge of the corresponding sector
    counterclockwise_point: str
    #Label of a point on the clockwise edge of the corresponding sector
    clockwise_point: str
    #Radius of the arc
    radius: float

    def __init__(self, ccw_point: str, center: str, cw_point: str, radius: float):
        self.counterclockwise_point = ccw_point
        self.center = center
        self.clockwise_point = cw_point
        self.radius = radius

    #Return [start angle, end angle] of the arc given a dictionary of points
    def calculate_angles(self, vertices: dict):
        center = vertices.get(self.center)
        start_point = vertices.get(self.counterclockwise_point)
        end_point = vertices.get(self.clockwise_point)
        if (center is None or start_point is None or end_point is None):
            return None
        center = center.coordinates
        start_point = start_point.coordinates
        end_point = end_point.coordinates
        x_difference = np.array([start_point[0] - center[0], end_point[0] - center[0]])
        y_difference = np.array([start_point[1] - center[1], end_point[1] - center[1]])
        radians = np.arctan(np.divide(y_difference, x_difference))
        degrees = (radians * 180 / np.pi).tolist()
        for i in range(2):
            if (x_difference[i] < 0):
                degrees[i] = degrees[i] + 180
        if (degrees[1] - degrees[0] > 0):
            degrees[1] = degrees[1] - 360
        return degrees
    
class angle:
    #Label of the point at the angle's center
    center: str
    #Label of a point on the counterclockwise edge of the angle
    counterclockwise_point: str
    #Label of a point on the clockwise edge of the angle
    clockwise_point: str
    #Measure label of the angle
    measure = ""

    def __init__(self, ccw_point: str, center: str, cw_point: str, raw_measure: str):
        self.counterclockwise_point = ccw_point
        self.center = center
        self.clockwise_point = cw_point
        if re.search(r"[A-Za-z_]", raw_measure):
            self.measure = raw_measure
        else:
            self.measure = evaluate_expression(raw_measure)

    #Return [start angle, end angle] of the angle given a dictionary of points
    def calculate_angles(self, vertices: dict):
        center = vertices.get(self.center)
        start_point = vertices.get(self.counterclockwise_point)
        end_point = vertices.get(self.clockwise_point)
        if (center is None or start_point is None or end_point is None):
            return None
        center = center.coordinates
        start_point = start_point.coordinates
        end_point = end_point.coordinates
        x_difference = np.array([start_point[0] - center[0], end_point[0] - center[0]])
        y_difference = np.array([start_point[1] - center[1], end_point[1] - center[1]])
        radians = np.arctan(y_difference / x_difference)
        degrees = (radians * 180 / np.pi).tolist()
        for i in range(2):
            if (x_difference[i] < 0):
                degrees[i] = degrees[i] + 180
        if (degrees[1] - degrees[0] > 0):
            degrees[1] = degrees[1] - 360
        return degrees

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
    #Old regex extended
    vertices_regex = re.compile(
        r"Vertex\s*([A-Z])\s*\:\s*\(([^,]+)\s*,\s*(.+)\s*\)\s*(above left|above right|below left|below right|above|below|left|right)?", 
        re.IGNORECASE,
    )

    # mine before
    # vertices_regex = re.compile(
    #     r"Vertex\s*([A-Z])\s*:\s*\(\s*([^,]+)\s*,\s*((?:[^()]|\([^()]*\))+)\s*\)\s*(above left|above right|below left|below right|above|below|left|right)?",
    #     re.IGNORECASE,
    # )

    # Old regex:
    # vertices_regex = re.compile(
    #     r"Vertex\s*([A-Z])\s*\:\s*\(([^,]+)\s*,\s*(.+)\s*\)", re.IGNORECASE)


    for match in vertices_regex.finditer(topology):
        name = match.group(1).upper()
        x = evaluate_expression(match.group(2).strip())
        y = evaluate_expression(match.group(3).strip())
        label_position = match.group(4)

        if label_position is None:
            label_position = None
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

    #Regex looking for a substring of the format "Circle [Label] Center [Center Point] Radius [Radius]" with optional whitespace
    circles_regex = re.compile(r"Circle\s*([A-Z])\s*Center\s*([A-Z])\s*Radius(.+)", re.IGNORECASE)

    for match in circles_regex.finditer(topology):
        label = match.group(1)
        center = match.group(2)
        radius = evaluate_expression(match.group(3).strip())
        circles.append([center, radius])

    #List containing all angles of the graph, BRYAN ADDED NICK PLS CHECK
    angles = []

    #Regex looking for a substring of the format "Angle [Angle Name] = [Angle Measure]" with optional whitespace
    angles_regex = re.compile(r"Angle\s*([A-Z]{3})\s*=\s*(.+)", re.IGNORECASE)

    for match in angles_regex.finditer(topology):
        angle_name = match.group(1).upper()
        raw_measure = match.group(2).strip()

        counterclockwise_point = angle_name[0]
        center = angle_name[1]
        clockwise_point = angle_name[2]

        angles.append(angle(counterclockwise_point, center, clockwise_point, raw_measure))

    #List containing all arcs of the graph
    arcs = []

    #Regex looking for a substring of the format "Arc [Counterclockwise endpoint][Center][Clockwise endpoint] Radius [radius]" with optional whitespace
    arcs_regex = re.compile(r"Arc\s*([A-Z]{3})", re.IGNORECASE)

    for match in arcs_regex.finditer(topology):
        arc_name = match.group(1).upper()

        counterclockwise_point = arc_name[0]
        center = arc_name[1]
        clockwise_point = arc_name[2]

        counterclockwise_vertex = vertices.get(counterclockwise_point)
        center_vertex = vertices.get(center)
        clockwise_vertex = vertices.get(clockwise_point)

        if (counterclockwise_vertex is None or center_vertex is None or clockwise_vertex is None):
            continue

        radius = math.dist(center_vertex.coordinates, clockwise_vertex.coordinates)

        arcs.append(arc(counterclockwise_point, center, clockwise_point, radius))

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

    #Check for maximum sizes to scale the image to fit
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

    if angles is not None:
        for angle in angles:
            counterclockwise_point = vertices.get(angle.counterclockwise_point).coordinates
            center = vertices.get(angle.center).coordinates
            clockwise_point = vertices.get(angle.clockwise_point).coordinates

            # Angles are drawn near the vertex.
            # This padding gives the angle marker and label some room.
            padding = 0.5

            min_x = min(min_x, counterclockwise_point[0], center[0] - padding, clockwise_point[0])
            max_x = max(max_x, counterclockwise_point[0], center[0] + padding, clockwise_point[0])
            min_y = min(min_y, counterclockwise_point[1], center[1] - padding, clockwise_point[1])
            max_y = max(max_y, counterclockwise_point[1], center[1] + padding, clockwise_point[1])
    
    if arcs is not None:
        for arc in arcs:
            center = vertices.get(arc.center).coordinates
            radius = arc.radius
            min_x = min(min_x, center[0] - radius)
            max_x = max(max_x, center[0] + radius)
            min_y = min(min_y, center[1] - radius)
            max_y = max(max_y, center[1] + radius)

    x_width = max_x - min_x
    y_width = max_y - min_y
    max_width = max(x_width, y_width)
    scale_factor = 18 / max_width

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
        
        for angle in angles:
            counterclockwise_point = [coordinate * scale_factor for coordinate in vertices.get(angle.counterclockwise_point).coordinates]
            center = [coordinate * scale_factor for coordinate in vertices.get(angle.center).coordinates]
            clockwise_point = [coordinate * scale_factor for coordinate in vertices.get(angle.clockwise_point).coordinates]

            print(counterclockwise_point)
            print(center)
            print(clockwise_point)

            angle_bounds = angle.calculate_angles(vertices)
            if angle_bounds is None:
                continue
            start_angle, end_angle = angle_bounds

            angle_value = angle.measure

            length1 = math.dist(vertex, counterclockwise_point)
            length2 = math.dist(vertex, clockwise_point)

            print(length1)
            print(length2)

            if length1 == 0 or length2 == 0:
                continue

            #Attempt to make the angle marking proportional to edge length while still bounded to [0.15, 0.45]
            marker_size = min(length1, length2) * 0.10
            marker_size = max(0.15, min(marker_size, 0.45))

            #Right angle marker
            if angle_value == 90:
                counterclockwise_edge_vector = [counterclockwise_point[0] - center[0] / length1, counterclockwise_point[1] - center[1] / length1]
                clockwise_edge_vector = [clockwise_point[0] - center[0] / length2, clockwise_point[1] - center[1] / length2]

                square_size = marker_size * 0.8

                a = TikZCoordinate(
                    center[0] + square_size * counterclockwise_edge_vector[0],
                    center[1] + square_size * counterclockwise_edge_vector[1]
                )

                b = TikZCoordinate(
                    center[0] + square_size * (counterclockwise_edge_vector[0] + clockwise_edge_vector[0]),
                    center[1] + square_size * (counterclockwise_edge_vector[1] + clockwise_edge_vector[1])
                )

                c = TikZCoordinate(
                    center[0] + square_size * clockwise_edge_vector[0],
                    center[1] + square_size * clockwise_edge_vector[1]
                )

                pic.append(
                    TikZDraw(
                        [a, "--", b, "--", c],
                        options = TikZOptions("line width = 0.8pt")
                    )
                )
            
            #Regular angle marker
            else:
                arc_start_x = center[0] + marker_size * math.cos(math.radians(start_angle))
                arc_start_y = center[1] + marker_size * math.sin(math.radians(start_angle))

                marker_start = TikZCoordinate(arc_start_x, arc_start_y)

                pic.append(
                    TikZDraw(
                        [marker_start, "arc"],
                        options = TikZOptions(
                            f"start angle  = {start_angle}",
                            f"end angle = {end_angle}",
                            "thick",
                            radius = marker_size
                        )
                    )
                )

                mid_angle = (start_angle + end_angle) / 2
                label_distancee = marker_size + 0.35

                label_coordinate = TikZCoordinate(
                    center[0] + label_distancee * math.cos(math.radians(mid_angle)),
                    center[1] + label_distancee * math.sin(math.radians(mid_angle))
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

        for arc in arcs:
            angles = arc.calculate_angles(vertices)
            if (angles is None):
                continue
            start_point = vertexCoordinates.get(arc.counterclockwise_point)
            if (start_point is None):
                continue
            pic.append(
                TikZDraw(
                    [start_point, "arc"],
                    options = TikZOptions(
                        f"start angle  = {angles[0]}",
                        f"end angle = {angles[1]}",
                        "thick",
                        radius = arc.radius * scale_factor
                    )
                )
            )
    
    doc.generate_pdf("tikzdraw", clean_tex = False)

    pdf_to_png("tikzdraw.pdf", "tikzdraw.png", dpi = dpi)
    pngpath = Path() / "tikzdraw.png"
    return pngpath.read_bytes()
