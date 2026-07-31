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
import os
import numpy as np
import math
from typing import List

class point:

    #Coordinates of the point's location
    coordinates: tuple[float]
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
        radians = np.arctan(y_difference / x_difference)
        degrees = (radians * 180 / np.pi).tolist()
        for i in range(2):
            if (x_difference[i] < 0):
                degrees[i] = degrees[i] + 180
        if (degrees[1] - degrees[0] > 0):
            degrees[1] = degrees[1] - 360
        return degrees


drawingInfo = {
    "vertices" : {
        "A" : point([-1, 1], "above left"),
        "B" : point([1, 1], "above right"),
        "C" : point([-math.sqrt(2), 0], "above left"),
        "D" : point([math.sqrt(2), 0], "above right"),
        "O" : point([0, 0], "below"),
        "P" : point([0, 1], None),
        "Z" : point([-10, 0], None)
    },
    "edges" : [
        ["A", "B"],
        ["O", "C"],
        ["O", "D"]
    ],
    "circles" : [
        ["O", math.sqrt(2)]
    ],
    "arcs" : {
        "APB" : arc("A", "P", "B", 1),
        "AOB" : arc("A", "O", "B", math.sqrt(2)),
        "DOC" : arc("D", "O", "C", math.sqrt(2))
    },
    "shaded regions" : [
        ["APB", "BOA"],
        ["AO", "OB", "BA"],
        ["COD", "DO", "OC"]
    ]
}

doc = Document()

doc.preamble.append(Command('pagestyle', 'empty'))

doc.preamble.append(Command('usepackage', 'geometry'))
doc.preamble.append(Command('geometry', 'margin = 0.1in'))

vertices = drawingInfo.get("vertices")
edges = drawingInfo.get("edges")
circles = drawingInfo.get("circles")
arcs = drawingInfo.get("arcs")
shaded_regions = drawingInfo.get("shaded regions")

min_x = 0
max_x = 0
min_y = 0
max_y = 0

vertexCoordinates = dict()
adjustedVertexCoordinates = dict()

rawVertexCoordinates = np.array([vertex.coordinates for vertex in vertices.values() if vertex.label_position is not None])

for vertexName in vertices.keys():
    point = vertices.get(vertexName)
    vertex = point.coordinates
    coordinate = TikZCoordinate(vertex[0], vertex[1])
    vertexCoordinates.update({vertexName : coordinate})
    min_x = min(rawVertexCoordinates[:, 0])
    max_x = max(rawVertexCoordinates[:, 0])
    min_y = min(rawVertexCoordinates[:, 1])
    max_y = max(rawVertexCoordinates[:, 1])

for circle in circles:
    center = vertices.get(circle[0]).coordinates
    radius = circle[1]
    min_x = min(min_x, center[0] - radius)
    max_x = max(max_x, center[0] + radius)
    min_y = min(min_y, center[1] - radius)
    max_y = max(max_y, center[1] + radius)

for arcName in arcs.keys():
    arc = arcs.get(arcName)
    center = vertices.get(arc.center).coordinates
    radius = arc.radius
    min_x = min(min_x, center[0] - radius)
    max_x = max(max_x, center[0] + radius)
    min_y = min(min_y, center[1] - radius)
    max_y = max(max_y, center[1] + radius)

x_width = max_x - min_x
y_width = max_y - min_y
max_width = max(x_width, y_width)
scale_factor = 20 / max_width

with doc.create(TikZ()) as pic:

    for vertexName in vertices.keys():
        point = vertices.get(vertexName)
        vertex = [coordinate * scale_factor for coordinate in point.coordinates]
        adjustedVertexCoordinates.update({vertexName : vertex})
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
                    options = TikZOptions(fill = "black", radius = 0.04)
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
                options = TikZOptions("thick")
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
                options = TikZOptions("thick", radius = radius * scale_factor)
            )
        )
    
    for arcName in arcs.keys():
        arc = arcs.get(arcName)
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

    for shaded_region in shaded_regions:
        start_point = shaded_region[0][0]
        #Do not render a shaded region if the first point of a border is invalid
        coordinates = adjustedVertexCoordinates.get(start_point)
        if (coordinates is None):
            break
        region_command = f"\\fill[black!25] ({coordinates[0]}, {coordinates[1]})"
        current_point = start_point
        for border in shaded_region:
            #Do not render a shaded region if the borders don't form a continuous path
            if (border[0] != current_point):
                break
            #Do not render a shaded region if the first point of a border is invalid
            if (adjustedVertexCoordinates.get(border[0]) is None):
                break
            #Check if the border is a line segment
            if (len(border) == 2):
                current_point = border[1]
                #Do not render a shaded region if a border takes you to an invalid point
                coordinates = adjustedVertexCoordinates.get(current_point)
                if (coordinates is None):
                    break
                region_command = region_command + f" -- ({coordinates[0]}, {coordinates[1]})"
            elif (len(border) == 3):
                current_point = border[2]
                #Do not render a shaded region if a border takes you to an invalid point or uses an invalid point as the center of the arc
                coordinates = adjustedVertexCoordinates.get(current_point)
                if (coordinates is None or adjustedVertexCoordinates.get(border[1]) is None):
                    break
                #Check the arcs dictionary for the arc in both directions to determine orientation
                #Default orientation is clockwise
                arc = arcs.get(border)
                if (arc is None):
                    #If default orientation is not found, check counterclockwise orientation by reversing the arc order
                    arc = arcs.get(border[::-1])
                    #Do not render a shaded region if a border is invalid
                    if (arc is None):
                        break
                    angles = arc.calculate_angles(vertices)[::-1]
                else:
                    angles = arc.calculate_angles(vertices)
                #Do not render the shaded region if the angle calculation fails
                if (angles is None):
                    break
                region_command = region_command + f" arc[start angle = {angles[0]}, end angle = {angles[1]}, radius = {arc.radius * scale_factor}]"
        else:
            region_command = region_command + ";"
            pic.append(
                TikZUserPath(region_command)
            )

doc.generate_pdf("tikzdraw", clean_tex = False)