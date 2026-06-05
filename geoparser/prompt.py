"""
Prompt templates for converting geometry diagrams into parser-friendly text.
"""

GEOMETRY_EXTRACTION_PROMPT = """
When I send you a geometry diagram, convert it into a clean parser-friendly text format.

Your task:
1. Identify all important points/vertices in the diagram.
2. Assign concrete coordinates that preserve the important geometry.
3. Do not use unresolved variables like s, r, a, h, x, etc.
4. If a coordinate depends on a given condition, solve just enough to substitute an exact value.
5. List all visible line segments.
6. List only the angles that are explicitly marked or labeled in the diagram.
7. List all circles/arcs if present.
8. Add helper points when needed for arc endpoints, intersections, or shaded-region boundaries.
9. Add label positions only when useful to avoid overlap.

Output format example:

example = \"\"\"
O is at (0,0)
A is at (-1,1)
B is at (1,1)
C is at (sqrt(2),0)
D is at (-sqrt(2),0)
P is at (0,1)
...

line segments AB BC CD DA AO BO ...

angles AOB=90 BOC=45 AOD=45 ...

circle C1 center O radius sqrt(2)

arcs APB[above]

shade APB[above] BOA fill gray!50
\"\"\"

General rules:
- Output only the `example = \"\"\" ... \"\"\"` block.
- Do not include explanations, derivations, bullet points, or commentary outside the block.
- Use Python-style math expressions:
  - `sqrt(3)`, not `sqrt3`
  - `2*sqrt(3)`, not `2sqrt3`
  - `pi`, `sin(pi/3)`, `cos(pi/3)` if needed
  - `2*sin(2*pi/3)`, not `2sin(2pi/3)`
- Use exact coordinates.
- Preserve the visual and geometric structure, not exact pixel positions.
- Do not solve the full problem unless I ask.
- Only solve enough to create valid coordinates.
- Do not include angles or arcs unless they are actually marked or drawn in the diagram.
- Include visible vertices and line segments needed to reproduce the diagram.

Coordinate rules:
- Choose a simple coordinate system that makes the diagram easy to render.
- If the original diagram gives a large length like 30, you may scale it down for the parser if the shape is preserved.
  - Example: a diameter labeled 30 may be represented using radius 3 instead of radius 15, unless the actual length is needed.
- Do not use huge coordinates unless necessary.
- Keep symmetry visible whenever possible.
- Put important symmetry axes on the x-axis or y-axis when convenient.
- All coordinates must be concrete numbers or valid Python-style expressions.
- Never output unresolved variables like `s`, `r`, `h`, `a`, `x`.

Point rules:
- Include all labeled points from the diagram.
- If a shaded boundary or arc boundary passes through an unlabeled point, create a helper point such as P, Q, R, I, J, K, etc.
- Helper points must have concrete coordinates.
- Helper points may be used in arcs and shade paths even if they are not labeled in the original diagram.
- Do not create unnecessary helper points that are not used.

Line segment rules:
- Include visible straight segments needed to reproduce the diagram.
- For line segments, use two-letter notation:
  - `AB` means segment from A to B.
- Only include a `line segments ...` line if there are visible straight segments.

Angle rules:
- Only include an `angles ...` line if the diagram explicitly marks or labels angles.
- Do not include inferred angles just because they can be determined.
- For angles, use three-letter notation:
  - `ABC=60` means angle ABC is 60 degrees, with B as the vertex.

Circle rules:
- Only use `circle ...` for complete circles that are actually drawn.
- Do not create full circles just because an arc belongs to that circle.
- For circles, define the center point first:
  - `O is at (0,0)`
  - `circle C1 center O radius 1`
- If a complete circle's center is not labeled, create a reasonable center name like O, O1, O2, etc.
- If only part of a circle is drawn, use `arcs ...`, not `circle ...`.

Arc rules:
- For arcs, use three-letter notation:
  - `ABC` means arc from A to C centered at B.
  - The middle letter is always the center of the arc.
- The first and third letters must be actual arc endpoints.
- The middle letter must be the center of the circle containing the arc.
- Do not write invalid arc tokens where the start, center, or end point are the same point.
  - Bad: `QQA`
  - Bad: `PPA`
- If the desired arc is ambiguous, especially for semicircles, add a bracket tag:
  - `ABC[above]`
  - `ABC[below]`
  - `ABC[left]`
  - `ABC[right]`
- Use `[above]`, `[below]`, `[left]`, or `[right]` for semicircles whenever the side matters.
- Examples:
  - `OAX[above]` means arc from O to X centered at A, drawn above diameter OX.
  - `YBO[right]` means arc from Y to O centered at B, drawn on the right side of diameter YO.
  - `ABC[below]` means arc from A to C centered at B, drawn below diameter AC.
- If the arc is clearly the minor arc and not ambiguous, no bracket tag is needed.
- Only include arcs that are actually drawn in the diagram.

Shading rules:
- If a shaded region appears, include one or more `shade ...` lines.
- A shade path is written as connected boundary tokens in order.
- A two-letter token like `AB` means straight segment from A to B.
- A three-letter token like `ABC` means arc from A to C centered at B.
- A shade path may mix straight segments and arcs.
- The shade path must trace the region boundary in connected order.
  - The end of each token must match the start of the next token.
  - The last token should end where the first token started, so the region closes.
- If a shaded boundary passes through an unlabeled intersection point, create a helper point and use it in the shade path.
- If an arc in a shade path is a semicircle or could be drawn on either side, include `[above]`, `[below]`, `[left]`, or `[right]`.
- Use `fill gray!50` or another simple TikZ fill color if needed.
- If there are multiple disconnected shaded regions, use multiple `shade ...` lines.
- Do not invent shaded regions that are not shown.

Validation checklist before output:
- Every point used in a line segment, angle, circle, arc, or shade path must be defined.
- Every arc token must have three distinct point letters.
- Every arc token `ABC` must mean: start A, center B, end C.
- Do not list full circles unless full circles are visible.
- Do not list arcs unless the arc is visible or is part of a shaded boundary.
- Every `shade ...` path must be connected in order.
- No unresolved variables are allowed.
- The final output should be parser-friendly, not a solution explanation.
- Preserve the visual and geometric structure, not exact pixel positions.
- Do not solve the full problem unless I ask.
- Only solve enough to create valid coordinates.
"""