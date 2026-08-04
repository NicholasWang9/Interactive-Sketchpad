import re

def parse_edges_from_topology(topology: str, topologyDict:dict) -> list:
    #List containing all edges of the graph
    edges = []

    #Regex looking for a substring of the format "Segment [Endpoint 1]-[Endpoint 2]" with optional whitespace
    edges_regex = re.compile(r"Segment\s*([A-Z])\s*\-\s*([A-Z])")
    
    for match in edges_regex.finditer(topology):
        endpoint1 = match.group(1)
        endpoint2 = match.group(2)
        edges.append([endpoint1, endpoint2])

    topologyDict.update({"edges" : edges})
    return edges

    