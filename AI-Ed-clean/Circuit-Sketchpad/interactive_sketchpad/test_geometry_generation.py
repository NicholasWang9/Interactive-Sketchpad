import geometry_components

input_string = """Vertex A:(100,0) right
Vertex B:(50,50*sqrt(3)) above right
Vertex C:(-50,50*sqrt(3)) above left
Vertex D:(-100,0) left
Vertex E:(-50,-50*sqrt(3)) below left
Vertex F:(50,-50*sqrt(3)) below right
Vertex P:(25,75*sqrt(3)) above
Vertex Q:(25,-75*sqrt(3)) below
Vertex R:(0,50*sqrt(3)) above
Vertex S:(0,-50*sqrt(3)) below

Segment A-B
Segment B-C
Segment C-D
Segment D-E
Segment E-F
Segment F-A
Segment A-P
Segment Q-A
Segment B-R
Segment P-B
Segment F-Q
Segment S-F

Arc PAQ
Arc RBP
Arc QFS

Shade AP PAQ QA
Shade BR RBP PB
Shade FQ QFS SF"""

geometry_components.generate(input_string)