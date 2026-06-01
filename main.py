"""
main.py
=======
Try out geoparser examples here.  Run with:

    python main.py
"""

from geoparser import geometry_to_latex

example = """
O is at (0,0)
A is at (0,3)
B is at (3*cos(pi/3),3*sin(pi/3))
C is at (3*cos(-pi/6),3*sin(-pi/6))
D is at (3*cos(11*pi/9),3*sin(11*pi/9))

line segments OA OB OC OD

angles AOB=30 BOC=90 COD=110 DOA=130

circle Circle1 center O radius 3
"""

if __name__ == "__main__":
    print(geometry_to_latex(example))