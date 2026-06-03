"""
main.py
=======
Try out geoparser examples here.  Run with:

    python main.py
"""

from geoparser import geometry_to_latex

example = """
A is at (0,0)
B is at (6,0)
C is at (3,3)
D is at (6,3)
E is at (7.5,1.5)
F is at (7.5,0)

line segments AB AC CB CD DB DE EB EF FB

angles BAC=45 ACB=90 BCD=45 CDB=90 DBE=45 DEB=90 BEF=45 EFB=90
"""

if __name__ == "__main__":
    print(geometry_to_latex(example))