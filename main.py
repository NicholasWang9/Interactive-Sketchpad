"""
main.py
=======
Try out geoparser examples here.  Run with:

    python main.py
"""

from geoparser import geometry_to_latex

# example = """
# A is at (0,0)
# B is at (6,0)
# C is at (6,6)
# D is at (0,6)

# line segments AB BC CD DA

# arcs DAB DCB
# """

example = """
A is at (0,0)
B is at (6,0)
C is at (6,6)
D is at (0,6)

line segments AB BC CD DA AC

arcs ABC DCB
"""

if __name__ == "__main__":
    print(geometry_to_latex(example))