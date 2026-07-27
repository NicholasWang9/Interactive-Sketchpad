import re
import math
import geometry_components_utilities as utilities

class point:

    #Coordinates of the point's location
    coordinates: tuple[float, float]
    #Planned location of the label
    label_position: str

    def __init__(self, coordinates, label_position = None):
        self.coordinates = coordinates
        self.label_position = label_position

def parse_vertices_from_topology(topology: str, topologyDict: dict) -> dict:
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
        x = utilities.evaluate_expression(match.group(2).strip())
        y = utilities.evaluate_expression(match.group(3).strip())
        label_position = match.group(4)

        if label_position is None:
            label_position = None
        else:
            label_position = label_position.lower()

        vertices.update({name : point((x, y), label_position)})

    topologyDict.update({"vertices" : vertices})
    return vertices