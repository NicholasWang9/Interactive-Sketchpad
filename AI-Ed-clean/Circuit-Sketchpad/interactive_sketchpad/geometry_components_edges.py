import re
import geometry_components_utilities as utilities

def parse_edges_from_topology(topology: str, topologyDict:dict) -> list:
    #List containing all edges of the graph
    edges = []

    #Regex looking for a substring of the format "Edge [Endpoint 1]-[Endpoint 2]", optionally
    #followed by "Label [expression] [position]" (e.g. "Edge A-B Label 4*sqrt(3) below"),
    #with optional whitespace. Position vocabulary matches Vertex label positions.
    #Position is not defaulted here -- an omitted position is left as None.
    edges_regex = re.compile(
        r"Edge\s*([A-Z])\s*\-\s*([A-Z])"
        r"(?:\s+Label\s+(\S+)(?:\s+(above left|above right|below left|below right|above|below|left|right))?)?"
    )

    for match in edges_regex.finditer(topology):
        endpoint1 = match.group(1)
        endpoint2 = match.group(2)
        raw_label = match.group(3)
        label = utilities.label_to_latex(raw_label) if raw_label else None
        position = match.group(4).lower() if match.group(4) else None
        edges.append([endpoint1, endpoint2, label, position])

    topologyDict.update({"edges" : edges})
    return edges

    