"""
main.py
=======
Try out geoparser examples here.  Run with:

    python main.py
"""

from geoparser import geometry_to_latex

example = """
O is at (0,0)
X is at (4,0)
Y is at (0,4)
M is at (2,0)
N is at (0,2)

line segments OX OY

arcs XOY[ccw] YNO[right] XMO[above]
"""

if __name__ == "__main__":
    print(geometry_to_latex(example))