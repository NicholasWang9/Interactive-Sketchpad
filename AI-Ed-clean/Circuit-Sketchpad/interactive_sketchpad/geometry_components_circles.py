import re
import geometry_components_utilities as utilities

def parse_circles_from_topology(topology: str, topologyDict: dict) -> list:
    #List containing all circles of the graph
    circles = []

    #Regex looking for a substring of the format "Circle [Label] Center [Center Point] Radius [Radius]" with optional whitespace
    circles_regex = re.compile(r"Circle\s*([A-Z])\s*Center\s*([A-Z])\s*Radius(.+)", re.IGNORECASE)
    
    for match in circles_regex.finditer(topology):
        label = match.group(1)
        center = match.group(2)
        radius = utilities.evaluate_expression(match.group(3).strip())
        circles.append([center, radius])

    topologyDict.update({"circles" : circles})
    return circles

    