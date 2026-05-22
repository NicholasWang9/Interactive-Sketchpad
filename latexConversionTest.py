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

drawingInfo = {
    "vertices" : {
        "A" : [0, 0],
        "B" : [0, 2],
        "C" : [2, 0],
        "D" : [-2, 0],
        "E" : [3, -4]
    },
    "edges" : [["A", "B"], ["A", "C"], ["B", "C"], ["A", "D"], ["E", "B"], ["F", "A"]],
    "circles" : [["A", 2], ["A", 5]]
}

doc = Document()

vertices = drawingInfo.get("vertices")
edges = drawingInfo.get("edges")
circles = drawingInfo.get("circles")

with doc.create(TikZ()) as pic:
    
    vertexCoordinates = dict()

    for vertexName in vertices.keys():
        vertex = vertices.get(vertexName)
        vertexCoordinates.update({vertexName : TikZCoordinate(vertex[0], vertex[1])})
        node = TikZNode(
            handle = vertexName,
            at = TikZCoordinate(vertex[0], vertex[1]),
            text = vertexName,
            options = TikZOptions("above left")
        )
        pic.append(node)
        pic.append(
            TikZDraw(
                [vertexCoordinates.get(vertexName), "circle"],
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