"""
main.py
=======
Try out geoparser examples here.  Run with:

    python main.py
"""

from geoparser import geometry_to_latex

# square with two arcs
# example = """
# A is at (0,0)
# B is at (6,0)
# C is at (6,6)
# D is at (0,6)

# line segments AB BC CD DA

# arcs DAB DCB

# shade DAB BCD fill gray!50
# """


# square with diagonal
example = """
A is at (0,0)
B is at (4,0)
C is at (4,4)
D is at (0,4)
I is at (4-2*sqrt(2),4-2*sqrt(2))
P is at (4-2*sqrt(3),2)

line segments AB BC CD DA AC

arcs ABC DCB

shade AI ICP PBA fill gray!50
"""


# triangle
# example = """
# A is at (0,0)
# B is at (6,0)
# C is at (3,3*sqrt(3))
# D is at (3,0)
# E is at (3/2,3*sqrt(3)/2)
# F is at (9/2,3*sqrt(3)/2)

# line segments AB BC CA

# arcs EAD DBF FCE

# shade DBF FCE EAD fill gray!50
# """


# one quarter circle two semi circles
example = """
O is at (0,0)
X is at (4,0)
Y is at (0,4)
M is at (2,0)
N is at (0,2)
P is at (2,2)

line segments OX OY

arcs XOY OMX[above] YNO[right]

shade OMP PNO fill gray!50
shade YOX XMP PNY fill gray!50
"""


if __name__ == "__main__":
    print(geometry_to_latex(example))