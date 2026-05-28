from pylatex import (
    Document,
    TikZ,
    TikZCoordinate,
    TikZDraw,
    TikZNode,
    TikZPath,
    TikZOptions,
    TikZUserPath
)
import os
import numpy as np
import math
from typing import List

class point:

    #Coordinates of the point's location
    coordinates: List[int]
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
        return degrees


drawingInfo = {
    "vertices" : {
        "A" : point([-1, 1], "above left"),
        "B" : point([1, 1], "above right"),
        "C" : point([-math.sqrt(2), 0], "above left"),
        "D" : point([math.sqrt(2), 0], "above right"),
        "O" : point([0, 0], "below"),
        "P" : point([0, 1], None)
    },
    "edges" : [
        ["A", "B"],
        ["O", "C"],
        ["O", "D"]
    ],
    "circles" : [
        ["O", math.sqrt(2)]
    ],
    "arcs" : [
        arc("A", "P", "B", 1)
    ]
}

doc = Document()

vertices = drawingInfo.get("vertices")
edges = drawingInfo.get("edges")
circles = drawingInfo.get("circles")
arcs = drawingInfo.get("arcs")

with doc.create(TikZ()) as pic:
    
    vertexCoordinates = dict()

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
                    radius = arc.radius
                )
            )
        )

doc.generate_pdf("tikzdraw", clean_tex = False)