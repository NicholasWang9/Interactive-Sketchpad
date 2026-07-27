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

    #List containing all shaded regions of the graph
    shading = []

    #Regex looking for substrings like:
    #Shade AB BC CA
    #Shade ABC CD DA
    #Shade ABC CAB BCA
    #Shade AB BC CA blue
    #Shade AB BC CA fill blue
    #
    #For shade tokens:
    #AB means straight segment from A to B
    #ABC means clockwise arc from A to C centered at B
    shading_regex = re.compile(r"^\s*Shade\s+(.+)$", re.IGNORECASE | re.MULTILINE)
    shade_token_regex = re.compile(r"^[A-Z]{2,3}$", re.IGNORECASE)

    for match in shading_regex.finditer(topology):
        raw_shade = match.group(1).strip()
        raw_parts = raw_shade.split()

        fill_color = "gray!30"
        shade_tokens = raw_parts

        fill_index = None
        for index, raw_part in enumerate(raw_parts):
            if raw_part.lower() == "fill":
                fill_index = index
                break

        if fill_index is not None:
            shade_tokens = raw_parts[:fill_index]

            if fill_index + 1 < len(raw_parts):
                fill_color = raw_parts[fill_index + 1]

        elif len(raw_parts) > 0 and shade_token_regex.fullmatch(raw_parts[-1]) is None:
            fill_color = raw_parts[-1]
            shade_tokens = raw_parts[:-1]

        clean_tokens = []

        for shade_token in shade_tokens:
            shade_token = shade_token.strip().upper()

            if shade_token_regex.fullmatch(shade_token) is None:
                continue

            clean_tokens.append(shade_token)

        if len(clean_tokens) > 0:
            shading.append({
                "tokens" : clean_tokens,
                "fill" : fill_color,
            })

    drawingInfo = {
        "vertices" : vertices,
        "edges" : edges,
        "circles" : circles,
        "angles" : angles,
        "arcs" : arcs,
        "shading" : shading
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
    Command,
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
    shading = drawingInfo.get("shading")

    min_x = 0
    max_x = 0
    min_y = 0
    max_y = 0

    vertexCoordinates = dict()

    rawVertexCoordinates = [vertex.coordinates for vertex in vertices.values() if vertex.label_position is not None]

    #Check for maximum sizes to scale the image to fit
    if vertices is not None:
        for vertexName in vertices.keys():
            point = vertices.get(vertexName)
            vertex = point.coordinates
        min_x = min([coordinate[0] for coordinate in rawVertexCoordinates])
        max_x = max([coordinate[0] for coordinate in rawVertexCoordinates])
        min_y = min([coordinate[1] for coordinate in rawVertexCoordinates])
        max_y = max([coordinate[1] for coordinate in rawVertexCoordinates])

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
        
    if shading is not None:
        for shade in shading:
            shade_tokens = shade.get("tokens")

            if shade_tokens is None:
                continue

            for shade_token in shade_tokens:
                if len(shade_token) == 2:
                    start_name = shade_token[0]
                    end_name = shade_token[1]

                    start_point = vertices.get(start_name)
                    end_point = vertices.get(end_name)

                    if start_point is None or end_point is None:
                        continue

                    start = start_point.coordinates
                    end = end_point.coordinates

                    min_x = min(min_x, start[0], end[0])
                    max_x = max(max_x, start[0], end[0])
                    min_y = min(min_y, start[1], end[1])
                    max_y = max(max_y, start[1], end[1])

                elif len(shade_token) == 3:
                    start_name = shade_token[0]
                    center_name = shade_token[1]
                    end_name = shade_token[2]

                    start_point = vertices.get(start_name)
                    center_point = vertices.get(center_name)
                    end_point = vertices.get(end_name)

                    if start_point is None or center_point is None or end_point is None:
                        continue

                    start = start_point.coordinates
                    center = center_point.coordinates

                    radius = math.dist(center, start)

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
                    options = TikZOptions(point.label_position, "font=\\Large")
                )
                pic.append(node)
                pic.append(
                    TikZDraw(
                        [coordinate, "circle"],
                        options = TikZOptions(fill = "black", radius = 0.04, )
                    )
                )
        
        # Shading should be drawn first so edges, arcs, angles, and labels appear on top.
        # Approach: build one clear path representation from named segments/arcs,
        # then pass that whole path fragment as ONE TikZUserPath to TikZDraw.
        # This avoids consecutive TikZUserPath objects and does not use NoEscape.
        for shade in shading:
            shade_tokens = shade.get("tokens")
            fill_color = shade.get("fill", "gray!30")

            if shade_tokens is None or len(shade_tokens) == 0:
                continue

            first_token = shade_tokens[0]
            first_start_name = first_token[0]
            first_start_coordinate = vertexCoordinates.get(first_start_name)

            if first_start_coordinate is None:
                continue

            path_fragments = []

            for shade_token in shade_tokens:
                if len(shade_token) == 2:
                    end_name = shade_token[1]
                    end_point = vertices.get(end_name)

                    if end_point is None:
                        continue

                    end = [coordinate * scale_factor for coordinate in end_point.coordinates]

                    # Segment token AB means draw from current point to B.
                    path_fragments.append(f"-- ({end[0]},{end[1]})")

                elif len(shade_token) == 3:
                    start_name = shade_token[0]
                    center_name = shade_token[1]
                    end_name = shade_token[2]

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

                    # Shade token ABC means:
                    # A is the start point
                    # B is the center
                    # C is the end point
                    # Draw clockwise from A to C
                    ccw_delta = (end_angle - start_angle) % 360

                    if ccw_delta == 0:
                        clockwise_delta = -360
                    else:
                        clockwise_delta = ccw_delta - 360

                    # Arc token ABC means draw the arc from the current point to C.
                    path_fragments.append(
                        f"arc[start angle = {start_angle}, delta angle = {clockwise_delta}, radius = {radius}]"
                    )

            if len(path_fragments) == 0:
                continue

            path_fragments.append("-- cycle")
            path_after_start = " ".join(path_fragments)

            pic.append(
                TikZDraw(
                    [
                        first_start_coordinate,
                        TikZUserPath(path_after_start)
                    ],
                    options = TikZOptions(f"fill = {fill_color}", "draw = none")
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

            length1 = math.dist(center, counterclockwise_point)
            length2 = math.dist(center, clockwise_point)

            print(length1)
            print(length2)

            if length1 == 0 or length2 == 0:
                continue

            start = [coordinate * scale_factor for coordinate in start_point.coordinates]
            vertex = [coordinate * scale_factor for coordinate in center_point.coordinates]
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
                counterclockwise_edge_vector = [(counterclockwise_point[0] - center[0]) / length1, (counterclockwise_point[1] - center[1]) / length1]
                clockwise_edge_vector = [(clockwise_point[0] - center[0]) / length2, (clockwise_point[1] - center[1]) / length2]

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
                label_distance = marker_size + 0.35

                label_coordinate = TikZCoordinate(
                    center[0] + label_distance * math.cos(math.radians(mid_angle)),
                    center[1] + label_distance * math.sin(math.radians(mid_angle))
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
