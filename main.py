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
# example = """
# A is at (0,0)
# B is at (4,0)
# C is at (4,4)
# D is at (0,4)
# I is at (4-2*sqrt(2),4-2*sqrt(2))
# P is at (4-2*sqrt(3),2)

# line segments AB BC CD DA AC

# arcs ABC DCB

# shade AI ICP PBA fill gray!50
# """


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
# example = """
# O is at (0,0)
# X is at (4,0)
# Y is at (0,4)
# M is at (2,0)
# N is at (0,2)
# P is at (2,2)

# line segments OX OY

# arcs XOY OMX[above] YNO[right]

# shade OMP PNO fill gray!50
# shade YOX XMP PNY fill gray!50
# """


# circle triangle circle 
# example = """
# O is at (0,0)
# A is at (-4,4*sqrt(3))
# B is at (-4,-4*sqrt(3))
# C is at (8,0)
# D is at (4,0)
# E is at (-4,0)

# line segments AB BC CA OC

# circle C1 center O radius 8
# circle C2 center O radius 4

# arcs AOB AOC BOC

# shade AOB BA fill blue!25
# shade AOC CA fill blue!25
# shade BOC CB fill blue!25
# shade DOE EOD fill blue!25
# """

# yin yang
# example = """
# O is at (0,0)
# A is at (0,15)
# B is at (0,-15)
# P is at (0,5)
# Q is at (0,-5)
# C is at (0,10)
# D is at (0,-10)

# line segments AB

# circle C1 center O radius 15

# arcs AOB[left] AOB[right] APQ[right] PQB[left] ACP[right] QDB[left]

# shade AOB[left] BQP[left] PCA[right] fill blue!25
# shade AOB[right] BDQ[left] QPA[right] fill blue!25
# """

example = """
A is at (0,sqrt(3))
B is at (-1,0)
C is at (1,0)

line segments

circle C1 center A radius 2
circle C2 center B radius 2
circle C3 center C radius 2

shade BAC CBA ACB fill gray!50
"""














if __name__ == "__main__":
    print(geometry_to_latex(example))