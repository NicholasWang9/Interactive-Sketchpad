import re
import math
import geometry_components_utilities as utilities

def parse_shaded_regions_from_topology(topology: str, topologyDict: dict) -> list:
    #List containing all shaded_regions of the graph
    shaded_regions = []

    #Regex looking for a substring of the format "Shaded Region [Border] [Border] ..." with whitespace between each Border where each Border has 2-3 characters
    shaded_region_regex = re.compile(r"Shaded Region(?:\s+[A-Z]{2,3})+")

    #Regex defining a Border
    border_regex = re.compile(r"[A-Z]{2,3}")

    for match in shaded_region_regex.finditer(topology):
        #Create shaded regions that are lists of each border used in each shaded region
        shaded_regions.append([border.group() for border in border_regex.finditer(match.group())])

    topologyDict.update({"shaded regions" : shaded_regions})
    return shaded_regions