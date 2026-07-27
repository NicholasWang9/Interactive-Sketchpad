
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import geometry_components_utilities as utilities
import geometry_components_vertices as geo_vertices
import geometry_components_edges as geo_edges
import geometry_components_circles as geo_circles
import geometry_components_arcs_and_angles as geo_arcs_and_angles

def parse_topology_to_dict(topology: str) -> dict:

    drawingInfo = {}

    #List containing all vertices of the graph
    vertices = geo_vertices.parse_vertices_from_topology(topology, drawingInfo)

    #List containing all edges of the graph
    edges = geo_edges.parse_edges_from_topology(topology, drawingInfo)

    #List containing all circles of the graph
    circles = geo_circles.parse_circles_from_topology(topology, drawingInfo)

    #List containing all angles of the graph
    angles = geo_arcs_and_angles.parse_angles_from_topology(topology, drawingInfo)

    #List containing all arcs of the graph
    arcs = geo_arcs_and_angles.parse_arcs_from_topology(topology, drawingInfo)

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

        if edges is not None:
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

        if circles is not None:
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

        if angles is not None:
            for angle in angles:
                counterclockwise_point = [coordinate * scale_factor for coordinate in vertices.get(angle.counterclockwise_point).coordinates]
                center = [coordinate * scale_factor for coordinate in vertices.get(angle.center).coordinates]
                clockwise_point = [coordinate * scale_factor for coordinate in vertices.get(angle.clockwise_point).coordinates]

                angle_bounds = angle.calculate_angles(vertices)
                if angle_bounds is None:
                    continue
                start_angle, end_angle = angle_bounds

                angle_value = angle.measure

                length1 = math.dist(center, counterclockwise_point)
                length2 = math.dist(center, clockwise_point)

                if length1 == 0 or length2 == 0:
                    continue

                #Attempt to make the angle marking proportional to edge length while still bounded to [0.15, 0.45]
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

        if arcs is not None:
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

    utilities.pdf_to_png("tikzdraw.pdf", "tikzdraw.png", dpi = dpi)
    pngpath = Path() / "tikzdraw.png"
    return pngpath.read_bytes()