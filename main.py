"""
main.py
=======
Try out geoparser examples here.  Run with:

    python main.py
"""

from geoparser import geometry_to_latex

example = """
P is at (0,0)
A is at (-5,0)
B is at (-13,0)
C is at (-3.7400277132,-3.7400277132)
D is at (-8.6897751815,-8.6897751815)
O is at (-9.0000000000,-3.4298028947)

line segments PB PD

circle C1 center O radius 5.2691126289
"""

if __name__ == "__main__":
    print(geometry_to_latex(example))