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

    def __init__(self, coordinates, label_position):
        self.coordinates = coordinates
        self.label_position = label_position

drawingInfo = {
    "vertices" : {
        "A" : point([-1, 1], "above left"),
        "B" : point([1, 1], "above right"),
        "C" : point([-math.sqrt(2), 0], "above left"),
        "D" : point([math.sqrt(2), 0], "above right"),
        "O" : point([0, 0], "below"),
        "P" : point([0, 1], None)
    },
    "edges" : [["A", "B"], ["O", "C"], ["O", "D"]],
    "circles" : [["O", math.sqrt(2)], ["P", 1]]
}

doc = Document()

vertices = drawingInfo.get("vertices")
edges = drawingInfo.get("edges")
circles = drawingInfo.get("circles")

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
            TikZPath(
                [point1, "--", point2],
                options = TikZOptions("draw")
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