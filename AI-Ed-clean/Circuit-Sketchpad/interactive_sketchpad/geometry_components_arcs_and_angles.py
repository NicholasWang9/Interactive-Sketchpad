import re
import math
import numpy as np
import geometry_components_utilities as utilities

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
        radians = np.arctan(np.divide(y_difference, x_difference))
        degrees = (radians * 180 / np.pi).tolist()
        for i in range(2):
            if (x_difference[i] < 0):
                degrees[i] = degrees[i] + 180
        if (degrees[1] - degrees[0] > 0):
            degrees[1] = degrees[1] - 360
        return degrees
    
class angle:
    #Label of the point at the angle's center
    center: str
    #Label of a point on the counterclockwise edge of the angle
    counterclockwise_point: str
    #Label of a point on the clockwise edge of the angle
    clockwise_point: str
    #Measure label of the angle
    measure = ""

    def __init__(self, ccw_point: str, center: str, cw_point: str, raw_measure: str):
        self.counterclockwise_point = ccw_point
        self.center = center
        self.clockwise_point = cw_point
        if re.search(r"[A-Za-z_]", raw_measure):
            self.measure = raw_measure
        else:
            self.measure = utilities.evaluate_expression(raw_measure)

    #Return [start angle, end angle] of the angle given a dictionary of points
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

def parse_arcs_from_topology(topology: str, topologyDict: dict) -> dict:
    #Dict containing all arcs of the graph
    arcs = {}

    #Regex looking for a substring of the format "Arc [Counterclockwise endpoint][Center][Clockwise endpoint]" with optional whitespace
    arcs_regex = re.compile(r"Arc\s*([A-Z])[\s-]*([A-Z])[\s-]*([A-Z])")

    vertices = topologyDict.get("vertices")

    if vertices is None:
        return None
    
    for match in arcs_regex.finditer(topology):

        counterclockwise_point = match.group(1).upper()
        center = match.group(2).upper()
        clockwise_point = match.group(3).upper()

        arc_name = counterclockwise_point + center + clockwise_point

        counterclockwise_vertex = vertices.get(counterclockwise_point)
        center_vertex = vertices.get(center)
        clockwise_vertex = vertices.get(clockwise_point)

        if (counterclockwise_vertex is None or center_vertex is None or clockwise_vertex is None):
            continue

        radius = math.dist(center_vertex.coordinates, clockwise_vertex.coordinates)
        arcs.update({arc_name : arc(counterclockwise_point, center, clockwise_point, radius)})
    
    topologyDict.update({"arcs" : arcs})
    return arcs

def parse_angles_from_topology(topology: str, topologyDict: dict) -> list:
    #List containing all angles of the graph
    angles = []

    #Regex looking for a substring of the format "Angle [Angle Name] = [Angle Measure]" with optional whitespace
    angles_regex = re.compile(r"Angle\s*([A-Z]{3})\s*=\s*(.+)")

    vertices = topologyDict.get("vertices")
    
    if vertices is None:
        return None
    
    for match in angles_regex.finditer(topology):
        angle_name = match.group(1).upper()
        raw_measure = match.group(2).strip()

        counterclockwise_point = angle_name[0]
        center = angle_name[1]
        clockwise_point = angle_name[2]

        counterclockwise_vertex = vertices.get(counterclockwise_point)
        center_vertex = vertices.get(center)
        clockwise_vertex = vertices.get(clockwise_point)
        
        if (counterclockwise_vertex is None or center_vertex is None or clockwise_vertex is None):
            continue
    
        angles.append(angle(counterclockwise_point, center, clockwise_point, raw_measure))

    topologyDict.update({"angles" : angles})
    return angles