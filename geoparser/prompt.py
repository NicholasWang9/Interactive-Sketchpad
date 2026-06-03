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
7. List all circles/arcs if present, including their centers and radii when possible.
8. Add label positions only when useful to avoid overlap.

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

circle O center O radius sqrt(2)

arcs APB[above]
\"\"\"

Rules:
- Output only the `example = \"\"\" ... \"\"\"` block.
- Use Python-style math expressions:
  - `sqrt(3)`, not `sqrt3`
  - `2*sqrt(3)`, not `2sqrt3`
  - `pi`, `sin(pi/3)`, `cos(pi/3)` if needed
  - `2*sin(2*pi/3)`, not `2sin(2pi/3)`
- Use exact coordinates when possible.
- Approximate coordinates are okay only if exact coordinates are hard or unnecessary.
- Do not include angles or arcs unless they are actually marked or drawn in the diagram.
- Include visible vertices and line segments needed to reproduce the diagram.
- For line segments, use two-letter notation:
  - `AB` means segment from A to B.
- For angles, use three-letter notation:
  - `ABC=60` means angle ABC is 60 degrees, with B as the vertex.
- Only include an `angles ...` line if the diagram explicitly marks or labels angles.
- For circles, define the center point first:
  - `O is at (0,0)`
  - `circle C1 center O radius 1`
- If a circle center is not labeled, create a reasonable name like O, O1, O2, etc.

Arc rules:
- For arcs, use three-letter notation:
  - `ABC` means arc from A to C centered at B.
  - The middle letter is always the center of the arc.
- If the desired arc is ambiguous, especially for semicircles, add a bracket tag:
  - `ABC[above]`
  - `ABC[below]`
  - `ABC[left]`
  - `ABC[right]`
  - `ABC[cw]`
  - `ABC[ccw]`
- Use `[above]`, `[below]`, `[left]`, or `[right]` for semicircles whenever the side matters.
- Examples:
  - `OAX[above]` means arc from O to X centered at A, drawn above the diameter OX.
  - `YBO[right]` means arc from Y to O centered at B, drawn on the right side of the diameter YO.
  - `ABC[below]` means arc from A to C centered at B, drawn below the diameter AC.
- If the arc is clearly the minor arc and not ambiguous, no bracket tag is needed.
- Only include arcs that are actually drawn in the diagram.

Shading rules:
- If a shaded region appears, add a `shade ...` line.
- Use path tokens to describe the boundary of the shaded region in order.
- A two-letter token like `AB` means straight segment from A to B.
- A three-letter token like `ABC` means arc from A to C centered at B.
- The shade path must go around the region in connected order.
- Example:
  - `shade DAB BCD`
  means shade the region bounded by arc D→B centered at A and arc B→D centered at C.
- If no shading is present, do not include a shade line.

Other rules:
- Preserve the visual and geometric structure, not exact pixel positions.
- Do not solve the full problem unless I ask.
- Only solve enough to create valid coordinates.
"""