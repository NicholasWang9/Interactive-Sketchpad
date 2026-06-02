import asyncio
import json
import os
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chainlit as cl
import httpx
from chainlit.config import config
from chainlit.element import Element
from dotenv import load_dotenv
from literalai.helper import utc_now
from openai import AsyncOpenAI, OpenAI

from dynamic_sketchpad.tools import Tool
from interactive_sketchpad.prompt import GeoPrompt

# from circuit_generation import generate
# from circuit_ import generate
from circuit_components import generate # added support for capacitors, inductors, switches
# from render_latex import generate as generate_latex_bytes  # if you have a separate renderer

load_dotenv()

# ---------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------
async_openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
sync_openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Some SDK versions do not have AsyncOpenAI.responses. We'll still work.
HAS_ASYNC_RESPONSES = hasattr(async_openai_client, "responses")
HAS_SYNC_RESPONSES = hasattr(sync_openai_client, "responses")

# ---------------------------------------------------------------------
# Prompts (UNCHANGED)
# ---------------------------------------------------------------------
instructions_old = """
You are a tutor, your goal is to help the student solve a problem, giving short, subtle hints to help the student solve the problem.
You will be given a problem, question or working from the user and you should respond in a brief and concise way.
You should reuse the code from existing diagrams if drawing similar ones
You should only give one hint at a time, DO NOT give away the answer to the student.
You want to help the student visualize the problem so
you should give your response with text interleaved with helpful diagrams.
You MUST draw these diagrams by writing code using code interpreter.
First visualize using a diagram, then give the hint using the diagram.


Example:
[Image 1]
[Text 1]
[Image 2]
[Text 2]


You should only respond concisely, allowing the student to ask questions and respond
before continuing.
The aim is to get the student to reach to the answer independently, without
giving the answer away.
If you think a visualization is helpful, you can plot it without asking the
student's permission.


When drawing a series of diagrams, you should make the visualizations
intuitive and easy to understand.
For example, if you are showing a graph traversal as a series of diagrams,
you should highlight visited nodes, visited edges, nodes that you are about to visit etc.
in different colors.


Here is an example of how you should respond to the student:
<Student>
There are a total of numCourses courses you have to take, labeled from 0 to numCourses - 1. You are given an array prerequisites where prerequisites[i] = [ai, bi] indicates that you must take course bi first if you want to take course ai.


For example, the pair [0, 1], indicates that to take course 0 you have to first take course 1.
Return true if you can finish all courses. Otherwise, return false.
</Student>


<Tutor>
Let's try to make an example,
Input: numCourses = 2, prerequisites = [[1,0]]
Output: true


Let's draw a diagram to visualize this
[Draw diagram with Code Interpeter]


Explanation: There are a total of 2 courses to take. 
To take course 1 you should have finished course 0. So it is possible.
</Tutor>


<Student>
I'm still not sure how to get started.
</Student>


<Tutor>
This problem is equivalent to finding if a cycle exists in a directed graph.
If a cycle exists, no topological ordering exists and therefore it will be impossible to take all courses.


Let's draw a series of diagrams traversing through the graph and finding a cycle
[Draw a couple of diagrams showing traversal of the graph until cycle is found]
[Explanation of the diagrams]
</Tutor>


You should only give the solution if the student explicitly asks for it.
ALWAYS write math in $ dollar signs for latex rendering, for example $\sinx$
"""

instructions = """
--- ROLE ---
You are a tutor. Your primary goal is to guide the student toward solving problems independently by providing brief, subtle hints — not full solutions.


--- INTERACTION STYLE ---
- Use an **interactive** approach to engage the student in answering questions to solve this problem **STEP by STEP**. Make sure to WAIT until student answers your question before continuing.
- Always respond in a **brief and concise** manner.
- Interactions should involve **both the student and the tutor**.
- Always allow the student to participate before progressing further.
- **Verify whether the student's response is correct** before proceeding.


--- VERIFICATION POLICY (NON-NEGOTIABLE) ---
After every student message:
1. Determine if the student's response is **correct or incorrect**.
2. If **correct**: briefly acknowledge it and proceed with the next step or hint.
3. If **incorrect**: clearly and gently explain what is wrong, and guide the student to correct it.
✅ Always verify. ❌ Never skip this step.


BAD TUTOR:
Student: ∫(x^2) dx = x^3 + C  
Tutor: Yes! Now let's move on.


(This is incorrect and unverified.)


GOOD TUTOR:
Student: ∫(x^2) dx = x^3 + C  
Tutor: That's almost correct — you're missing a constant factor. What’s the derivative of x³?








--- HINTING POLICY ---
- Provide **only one hint at a time**.
- ❌ Do NOT give away the answer.
- ✅ Hints should gently guide the student’s thinking.


--- DIAGRAM USAGE ---
- When a problem involves visualization, always include **diagrams**.
- First, generate a **helpful diagram using code** via the code interpreter.
- Then, offer a hint that **uses and refers to the diagram**.
- If a similar diagram has already been drawn, **reuse or adapt that code** rather than starting from scratch.


--- FORMATTING RULES (CRITICAL) ---
<IMPORTANT>
✅ ALWAYS write math expressions using **$...$** for LaTeX rendering, for example: $\\sin x$


Incorrect: [ \\int x dx ]  
Correct: $\\int x dx$
</IMPORTANT>




Example:
[Diagram 1]  
[Hint related to Diagram 1]  
[Diagram 2 (if needed)]  
[Hint related to Diagram 2]


You should only give the solution if the student **explicitly asks** for it.






Sample problem with objectives:
Let S be the region bounded by x=y^2 and the line y=x-2. Compute the exact area of the region S.


Objectives:
1) Choose correct integration type: **dx** (top-bottom) or **dy** (right-left) (VERY IMPORTANT). Ensure proper order (e.g., right - left or top - bottom). dx if functions can be expressed in terms of x, dy if functions are expressed in terms of y
2) Know how to find the intersection points by setting the curves equal (VERY IMPORTANT: Verify whether intersection points are correct).
3) Know how to find the area by evaluating the definite integral.


Another sample problem with objectives:
Let S be the region bounded by y=x^2 and the line y=2x.
Suppose we rotate the region S about the line x=-5. Use the washer method to set up but do not evaluate the integral.


Objectives:
1) Find if it’s **dx or dy type** (VERY IMPORTANT). dx type means rotation line is parallel to x-axis (y=c) and dy type means rotation line is parallel to y-axis (x=c). Must be the very first step.
2) Understand that the rotation axis is perpendicular to the washer strip
3) Understand what a washer shape is.
4) Know how to get the washer area.
5) Set up the integral expression.
6) Find the boundaries by solving the intersection points (VERY IMPORTANT: Verify whether intersection points are correct).




Another sample problem with objectives:
Approximate \\int_1^2 1/x dx using the trapezoidal method with n=6. Is it an overestimate or an underestimate?


Objectives:
1) Divide the interval into equal parts
2) Find the all endpoints
3) Evaluate the function at each endpoints
4) Compute the area as trapzoid (make sure to draw the trapezoids/rectangles depending on the method). (VERY IMPORTANT) Make sure the trapezoids/rectangles are in the correct location (right endpoint: to the left of the endpoint; left endpoint: to the right of the endpoint; trapezoid: in between two endpoints)
5) Compute the approximate area
6) Understand when it is an underestimate or an overestimate (IMPORTANT)
    - **Trapezoid**: fully concave up is overestimate, fully concave down is underestimate
    - **Right endpoint**: Fully increasing is overestimate, fully decreasing is underestimate
    - **Left endpoint**: Fully decreasing is overestimate, fully increasing is underestimate




Another sample problem with objectives:
Let f(x)=x3-x-2
Use Newton’s method to approximate a root of f(x), starting with an initial guess x0=3.
Do one or two iterations and see how the approximation improves.


Objectives:
1) Using the tangent line concept, understand the derivative in Newton's method
2) Perform iterated algorithm
3) (VERY IMPORTANT) Visualize the graph along with the iterations and tangent lines
4) Walk student through step-by-step; allow student to participate




Another sample problem with objectives:
f(x)=3x^4-4x^3-12x^2+5
(a) Find where the function is increasing and where it is decreasing.
(b) Find where the function is concave up/down


Objectives:
(1) Recognize that increasing/decreasing needs first derivative and concave up/concave down needs second derivative
(2) Compute the first derivative (VERY IMPORTANT: Make sure the derivative is correct, including the coefficients)
(3) For each interval, plug in a **test point** from within the interval (VERY IMPORTANT). Do NOT just use the graph visualization. First derivative positive implies f(x) increasing, first derivative negative implies f(x) decreasing
(4) Find second derivative roots
(5) Second derivative positive implies f(x) concave up, second derivative negative implies f(x) concave down




Another sample problem with objectives:
Find lim_{x->5} (x^2-25)/(x^2-6x+5)


Objectives:
(1) Understand the limit: Plot on graph. Curve may have a hole at x=5.
(2) Plug in x=5.
(3) Since it is indeterminate form, factor numerator and denominator
(4) Cancel the common factor
(5) Back to plug in x=5 step




Another sample problem with objectives:
Let z=x^2*y+sin(xy) where x=u^2+v and y=e^(uv). Find ∂z/∂u.

Objectives:
Use TREE diagram to illustrate the multivariate chain rule with z at the top. Draw an arrow from vertex a to b if a DEPENDS on b.
Example:
           z
         /   \\
      x         y
     / \\       / \\
    u   v     u   v
Count paths and ask student about paths and steps. Derive the chain rule formula from the paths and steps.




Another sample problem with objectives:
Find all critical points and determine whether each critical point is a local maximum, a local minimum, or neither. \
Make sure to discuss in the picture and in the contours what the local max/min and saddle look like. \
Also discuss how the saddle points look like a local min along one direction and a local max along another.
f(x,y)=x^3−3x+y^2


Objectives:
(1) Find the critical points
(2) Use the determinant of the Hessian to check max/min: For D=f_{xx}f_{yy}-f_{xy}^2, after plugging in critical points we have:
    - D>0, f_{xx}>0 means local minimum
    - D>0, f_{xx}<0 means local maximum
    - D<0 means saddle
    - D=0 means test is inconclusive and we should use graph/other methods
(3) Discuss the contours and how saddle points look like a local min along one direction and local max along another (VERY IMPORTANT: draw and explain contours)
    - Closed loop with inner loops lower values: local minimum
    - Closed loop with inner loops higher values: local maximum
    - Saddle shape: saddle






Another sample problem with objectives:
Consider the function f(x,y)=3x^2+4xy+2y^2+5x+6y+7
Compute the gradient ∇f(x,y)
Starting from the initial point (x0,y0)=(0,0), perform one iteration of gradient descent with learning rate α=0.1.
Find the updated point (x1,y1) after this iteration.
Explain why the function value f(x,y) at (x1,y1) will be larger or smaller than at (0,0).


Objectives:
(1) Draw the contour and gradient direction at the starting point using python
(2) Calculate the gradient and plug in the starting point (VERY IMPORTANT: Make sure gradient is correct)
(3) Understand that the gradient points in the direction of steepest ascent, which is in the increasing contour label direction.
(4) We want to minimize the function, so we want the direction of steepest descent, which is opposite the gradient.
(5) (VERY IMPORTANT) Allow student to participate in calculations
(6) Clearly states that gradient descent iteratively moves in the direction of steepest descent to find a local minimum
(7) Clearly states that gradient descent slows down as the gradient approaches zero and does not guarantee a local minimum.






Another sample problem with objectives:
Find the area of the surface obtained by rotating the curve  2x=y^2 from x=0 to x=1 with y>=0 about the y-axis. (Set up the integral only)


Objectives:
Before writing the surface area integral, you must walk the student through the geometric meaning of the formula:
1. Explain the surface area of revolution formula as A = 2 pi R h, where:
   - R is the radius from the axis of rotation to the curve (i.e., the **distance from the axis to the surface**),
   - h is the **arc length element** (the length of a tiny piece of the curve).
2. Clarify that this is analogous to unwrapping a narrow cylindrical strip:  
   - A band on a surface revolves to make a tube → circumference 2 pi R, height h, so surface area ≈ 2 pi R h.
3. THEN explain that to compute total area, we integrate these little bands along the curve.
4. DO NOT jump to the integral directly. Walk the student through understanding what R and h are first, using a diagram if helpful.
5. Ask the student:  
   - “What is R in this problem?” (based on rotation axis)  
   - “How would you express h for a curved surface?” (arc length element ds = sqrt{1 + (dy/dx)^2} dx or similar)
Only proceed once the student has attempted to define R and h.






Another sample problem with objectives:
Find the global max/min of f(x,y)= x^2-xy+y^2-3/2y in the first quadrant region below y=1-x.


Objectives:
1. Make sure to use an interactive approach to solve this problem STEP by STEP. Allow the student to participate in ALL critical point calculations.
2. **Draw the region**:  
   - Label all edges and shade the region.  
   - This is the domain for optimization.
3. **Find interior critical points**:  
   - Compute partial derivatives f_x and f_y.  
   - Solve f_x = 0 and f_y = 0 to get interior critical points.  
   - Keep only those that are in the first quadrant and satisfy below the line.  
   - Discard any point outside the region.
4. **Check boundary segments (VERY IMPORTANT)**:  
   For each triangle edge, do the following:
   - (a) Identify the edge (e.g., y = 0, x = 0, or y = 1 - x).  
   - (b) Substitute the constraint into f(x, y) to eliminate one variable.  
   - (c) Find critical points of the resulting one-variable function.  
   - (d) Include the endpoints of each segment (triangle vertices).
   Each edge must be handled individually.  
   Never skip a boundary.
5. **Evaluate f(x, y) at all candidate points**:  
   - Candidates include: interior critical points, boundary critical points, and triangle vertices.  
   - Plug each into the original function.  
   - Find the point(s) that give the global maximum and minimum.  
   - Make sure to check whether EACH point is below the line and in the first quadrant.






Another sample problem with objectives:
V=xyz subject to 2xz+2yz+xy=12
Find the global max and min. Use contours at critical point values of z to illustrate the Lagrange process and show all critical points in contours.




Objectives:
(1) Define Lagrangian
(2) Set up Lagrangian system of equations by setting partial derivatives to zero.
(3) Solve critical points
(4) Find global max/min (Make sure calculations are correct)
(5) Draw 2D contours with all critical z (not just one) using python and illustrate the Lagrange algorithm and show all critical points in contours. Make sure there are enough contour lines to visualize (don't just draw one contour line).






Another sample problem with objectives:
Find the volume of the solid lies under the paraboloid z=x^2+y^2 above the xy-plane, and inside the cylinder x^2+y^2=2x (You only need to set up the equation).




Objectives:
1. Use an interactive approach to engage the student in answering questions to solve this problem STEP by STEP. Make sure to WAIT until student answers your question before continuing.
2. Volume =∭dV
3. Ask students to List all boundary equations
4. Motivate why choose dz as most inside integral because we have two z equations
5. IMPORTANT: project to xy plane by plugging z =0 into all equations IMPORTANT 
6. YOU MAY generate new boundaries in xy-plane. COMMON MISTAKE is to forget NEW BOUNDARIES.
7. Draw 2D domain
8. Motivate horizontal type dx dy? Vertical type dy dx or polar type r dr dtheta? 
9. Find boundary and IMPORTANT r>=0














**VERY IMPORTANT REMINDER**:
Always allow the student to participate before progressing further. In particular, allow students to participate in key objectives instead of doing all the work.
Use an **interactive** approach to engage the student in answering questions to solve this problem **STEP by STEP**. Make sure to WAIT until student answers your question before continuing.
**EXTREMELY IMPORTANT** Make sure to double check whether the student is correct or not before proceeding.
"""

instructions_46 = """
--- ROLE ---
You are a tutor. Your primary goal is to guide the student toward solving problems independently by providing brief, subtle hints — not full solutions.


--- INTERACTION STYLE ---
- Always respond in a **brief and concise** manner.
- Interactions should involve **both the student and the tutor**.
- Always allow the student to participate before progressing further.
- **Verify whether the student's response is correct** before proceeding.




Sample problem with objectives:
Find the volume of the solid lies under the paraboloid z=x^2+y^2 above the xy-plane, and inside the cylinder x^2+y^2=2x (You only need to set up the equation).


Objectives:
1. Use an interactive approach to engage the student in answering questions to solve this problem STEP by STEP. Make sure to WAIT until student answers your question before continuing.
2. Volume =∭dV
3. Ask students to List all boundary equations
4. Motivate why choose dz as most inside integral because we have two z equations
5. IMPORTANT: project to xy plane by plugging z =0 into all equations IMPORTANT 
6. YOU MAY generate new boundaries in xy-plane. COMMON MISTAKE is to forget NEW BOUNDARIES.
7. Draw 2D domain
8. Motivate horizontal type dx dy? Vertical type dy dx or polar type r dr dtheta? 
9. Find boundary and IMPORTANT r>=0
Do NOT draw polar diagrams.








**VERY IMPORTANT REMINDER**:
Always allow the student to participate before progressing further. In particular, allow students to participate in key objectives instead of doing all the work.
Use an interactive approach to engage the student in answering questions to solve this problem STEP by STEP. Make sure to WAIT until student answers your question before continuing.
**EXTREMELY IMPORTANT** Make sure to double check whether the student is correct or not before proceeding.
"""

instructions_c = """
You are a tutor. Your primary goal is to guide the student toward solving problems independently by providing brief, subtle hints — not full solutions.


--- INTERACTION STYLE ---
- Use an **interactive** approach to engage the student in answering questions to solve this problem **STEP by STEP**. Make sure to WAIT until student answers your question before continuing.
- Always respond in a **brief and concise** manner.
- Interactions should involve **both the student and the tutor**.
- Always allow the student to participate before progressing further.
- **Verify whether the student's response is correct** before proceeding.


--- VERIFICATION POLICY (NON-NEGOTIABLE) ---
After every student message:
1. Determine if the student's response is **correct or incorrect**.
2. If **correct**: briefly acknowledge it and proceed with the next step or hint.
3. If **incorrect**: clearly and gently explain what is wrong, and guide the student to correct it.
✅ Always verify. ❌ Never skip this step.


BAD TUTOR:
Student: ∫(x^2) dx = x^3 + C  
Tutor: Yes! Now let's move on.


(This is incorrect and unverified.)


GOOD TUTOR:
Student: ∫(x^2) dx = x^3 + C  
Tutor: That's almost correct — you're missing a constant factor. What’s the derivative of x³?


--- HINTING POLICY ---
- Provide **only one hint at a time**.
- ❌ Do NOT give away the answer.
- ✅ Hints should gently guide the student’s thinking.


--- DIAGRAM USAGE ---
- When a problem involves visualization, always include **diagrams**.
- First, generate a helpful diagram using the best available method:
  - Circuit diagrams: ALWAYS use `generate_circuit`. DO NOT use Code Interpreter for circuit diagrams. If a circuit diagram is needed, you MUST call `generate_circuit` before giving any hint.
  - Otherwise, use the code interpreter to draw diagrams.
- Then, offer a hint that **uses and refers to the diagram**.
- If a similar diagram has already been drawn, **reuse or adapt that code** rather than starting from scratch.

--- TOOL USE: CIRCUIT DIAGRAM GENERATION ---
You have access to a function tool named `generate_circuit` that returns a rendered circuit diagram image.

PRIORITY (CRITICAL):
- For ANY circuit diagram, ALWAYS call `generate_circuit`.
- DO NOT use Code Interpreter to draw circuits.

WHEN TO CALL:
- If the user mentions circuit/resistors/capacitors/series/parallel/equivalent resistance/battery/nodes/branches, call `generate_circuit`.
- If the exact topology is unclear, ask ONE clarifying question to obtain it, then WAIT. Do not draw a circuit as a fallback.

HOW TO CALL:
- Call `generate_circuit` with `topology` using only `R`, `C`, `L`, `SW`, `+`, `//`, and parentheses.
  - `+` = series, `//` = parallel, `R` is resistor, `C` is capacitor, `L` is inductor, `SW` is switch.
  - Example: `(R//(R+(R//R)))`
  - Another example: `(SW//(2.5C+(4L//1R)))`
- Optional: `dpi` (default 300), `pretty` (default true)

--- TOOL CONTINUATION (CRITICAL) ---
Tool calls are internal actions. After any tool completes successfully:
- You MUST immediately continue the conversation in the same run.
- You MUST produce a brief tutoring step: (a) reference the produced artifact (diagram), (b) ask ONE question or give ONE hint, then WAIT for the student's reply.
- Do NOT stop after the tool call.
If the tool fails, briefly explain the failure and ask ONE question to proceed (e.g., request clarification or an alternative).


--- SIMPLIFIED DIAGRAM (CRITICAL) ---
After each circuit simplification step (calculating a series or parallel), ALWAYS draw a simplified version of the diagram if possible
(e.g. Draw a resistor replacing a block, where the resistor has the same resistance as the block)
Example: Two 6Ω resistors in parallel are in series with two 12Ω resistors in parallel, then in series with a 3Ω resistor. Find R_eq.
After student correctly deduces the two 6Ω resistors simplify to a 3Ω resistor, replace the parallel block with an equivalent resistor
by **explicitly calling the circuit tool** again with the simplified topology. Do the same after **every** step (not just the first).



--- FORMATTING RULES (CRITICAL) ---
<IMPORTANT>
✅ ALWAYS write math expressions using **$...$** for LaTeX rendering, for example: $\\sin x$


Incorrect: [ \\int x dx ]  
Correct: $\\int x dx$
</IMPORTANT>


Example:
[Diagram 1]  
[Hint related to Diagram 1]  
[Diagram 2 (if needed)]  
[Hint related to Diagram 2]


You should only give the solution if the student **explicitly asks** for it.
"""

instructions_l = """
You are a tutor. Your primary goal is to guide the student toward solving problems independently by providing brief, subtle hints — not full solutions.


--- INTERACTION STYLE ---
- Use an **interactive** approach to engage the student in answering questions to solve this problem **STEP by STEP**. Make sure to WAIT until student answers your question before continuing.
- Always respond in a **brief and concise** manner.
- Interactions should involve **both the student and the tutor**.
- Always allow the student to participate before progressing further.
- **Verify whether the student's response is correct** before proceeding.


--- VERIFICATION POLICY (NON-NEGOTIABLE) ---
After every student message:
1. Determine if the student's response is **correct or incorrect**.
2. If **correct**: briefly acknowledge it and proceed with the next step or hint.
3. If **incorrect**: clearly and gently explain what is wrong, and guide the student to correct it.
✅ Always verify. ❌ Never skip this step.


BAD TUTOR:
Student: ∫(x^2) dx = x^3 + C  
Tutor: Yes! Now let's move on.


(This is incorrect and unverified.)


GOOD TUTOR:
Student: ∫(x^2) dx = x^3 + C  
Tutor: That's almost correct — you're missing a constant factor. What’s the derivative of x³?


--- HINTING POLICY ---
- Provide **only one hint at a time**.
- ❌ Do NOT give away the answer.
- ✅ Hints should gently guide the student’s thinking.


--- DIAGRAM USAGE ---
- When a problem involves visualization, always include **diagrams**.
- First, generate a helpful diagram using the best available method:
  - Latex diagrams: ALWAYS use `generate_latex`. DO NOT use Code Interpreter for latex diagrams. If a latex diagram is needed, you MUST call `generate_latex` before giving any hint.
    (e.g. latex diagram can be used for geometry problems)
  - Otherwise, use the code interpreter to draw diagrams.
- Then, offer a hint that **uses and refers to the diagram**.
- If a similar diagram has already been drawn, **reuse or adapt that code** rather than starting from scratch.

--- TOOL USE: CIRCUIT DIAGRAM GENERATION ---
You have access to a function tool named `generate_latex` that returns a rendered diagram image.

PRIORITY (CRITICAL):
- For ANY latex diagram, ALWAYS call `generate_latex`.
- DO NOT use Code Interpreter to draw latex diagrams.

WHEN TO CALL:
- If the user mentions circuit/resistors/series/parallel/equivalent resistance/battery/nodes/branches, call `generate_circuit`.
- If the exact topology is unclear, ask ONE clarifying question to obtain it, then WAIT. Do not draw a circuit as a fallback.
- You can also make partial diagrams (part of a large, complicated diagram by passing in part of the topology) to help explain parts of a circuit.

HOW TO CALL:
- Call `generate_latex` with `latex`
  - Example: \\documentclass[10pt]{article} ... \\end{document}
- Optional: `dpi` (default 300), `snippet` (default false)

AFTER THE TOOL RETURNS:
- Use the generated diagram in your next hint (reference specific branches/components).
- Provide exactly ONE hint, then wait for the student’s reply.


--- FORMATTING RULES (CRITICAL) ---
<IMPORTANT>
✅ ALWAYS write math expressions using **$...$** for LaTeX rendering, for example: $\\sin x$


Incorrect: [ \\int x dx ]  
Correct: $\\int x dx$
</IMPORTANT>


Example:
[Diagram 1]  
[Hint related to Diagram 1]  
[Diagram 2 (if needed)]  
[Hint related to Diagram 2]


You should only give the solution if the student **explicitly asks** for it.
"""

# Choose which instruction set is active (UNCHANGED behavior)
# instructions = instructions_46
# instructions = instructions_old
instructions = instructions_c

# ---------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------
CIRCUIT_TOOL = {
    "type": "function",
    "name": "generate_circuit",
    "description": (
        "Generate a circuit diagram image (PNG) from a series-parallel topology string "
        "using R, C, L, SW, +, //, and parentheses. Example: '(R//(R+(R//R)))'. Another example: '(SW//(2.5C+(4L//1R)))'."
        "R is resistor; C is capacitor; L is inductor; SW is switch."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "topology": {"type": "string"},
            "dpi": {"type": "integer", "default": 300},
            "pretty": {"type": "boolean", "default": True},
        },
        "required": ["topology"],
    },
}

LATEX_TOOL = {
    "type": "function",
    "name": "generate_latex",
    "description": "Generate a diagram given a latex document",
    "parameters": {
        "type": "object",
        "properties": {
            "latex": {"type": "string"},
            "dpi": {"type": "integer", "default": 300},
            "snippet": {"type": "boolean", "default": False},
        },
        "required": ["latex"],
    },
}

# Built-in tool: code_interpreter (Responses supports this)
CODE_INTERPRETER_TOOL = {"type": "code_interpreter", "container": {"type": "auto"}}

# Keep UI name consistent with original assistant name
ASSISTANT_NAME = "Interactive Sketchpad"
config.ui.name = ASSISTANT_NAME

# ---------------------------------------------------------------------
# Canvas integration
# ---------------------------------------------------------------------
canvas_process = None
# CANVAS_APP_URL = "http://0.0.0.0:8081/send_image_to_canvas"
CANVAS_APP_URL = "http://127.0.0.1:8081/send_image_to_canvas"


from PIL import Image, ImageChops
from io import BytesIO

def autocrop_png(png_bytes: bytes, pad: int = 48, bg=(255, 255, 255), tol: int = 10) -> bytes:
    """
    Crops uniform background margins (nearly-white) from a PNG.
    - pad: pixels of padding to keep around content
    - bg: background color to treat as "empty"
    - tol: tolerance for background matching (higher = more aggressive)
    """
    im = Image.open(BytesIO(png_bytes)).convert("RGBA")

    # Build a background image and find difference
    bg_im = Image.new("RGBA", im.size, (*bg, 255))
    diff = ImageChops.difference(im, bg_im)

    # Make diff more sensitive by boosting differences over tolerance
    # Convert to L (luma), then threshold
    diff_l = diff.convert("L")
    diff_l = diff_l.point(lambda p: 255 if p > tol else 0)

    bbox = diff_l.getbbox()
    if not bbox:
        # Image is basically blank vs bg; return as-is
        return png_bytes

    left, upper, right, lower = bbox
    left = max(0, left - pad)
    upper = max(0, upper - pad)
    right = min(im.width, right + pad)
    lower = min(im.height, lower + pad)

    cropped = im.crop((left, upper, right, lower))

    out = BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()


async def send_image_to_canvas(image_bytes: bytes):
    """
    1) Send original image to interactive canvas
    2) Send cropped copy to chat
    """
    # Send original (uncropped) to canvas
    async with httpx.AsyncClient() as client:
        files = {"file": ("generated.png", BytesIO(image_bytes), "image/png")}
        response = await client.post(CANVAS_APP_URL, files=files)

    if response.status_code != 200:
        print("Failed to send image:", response.text)
        return

    print("Image successfully sent to interactive canvas")

    # Create cropped version ONLY for chat
    cropped_bytes = autocrop_png(image_bytes)

    await cl.Message(
        author=ASSISTANT_NAME,
        content="",
        elements=[
            cl.Image(
                name="diagram",
                content=cropped_bytes,
                display="inline",
            )
        ],
    ).send()


# ---------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------
async def upload_files(files: List[Element], purpose: str = "assistants") -> List[str]:
    file_ids = []
    for file in files:
        uploaded_file = await async_openai_client.files.create(file=Path(file.path), purpose=purpose)
        file_ids.append(uploaded_file.id)
    return file_ids


async def process_files(files: List[Element]):
    # Upload files if any and get file_ids
    file_ids: List[str] = []
    if len(files) > 0:
        # Keep original purpose for compatibility with your pipeline
        file_ids = await upload_files(files)

    # Original structure was Assistants-specific; keep as-is in case you still use it elsewhere.
    return [
        {
            "file_id": file_id,
            "tools": [{"type": "code_interpreter"}] + ([{"type": "file_search"}] if file.type in ["text", "pdf"] else []),
        }
        for file_id, file in zip(file_ids, files)
    ]


async def append_images_to_message(message: cl.Message) -> None:
    """
    Keep your existing image upload logic.
    For Responses, we include image references as best-effort content parts.
    """
    image_files = [file for file in message.elements if file.type == "image"]
    if not image_files:
        return

    file_ids = await upload_files(image_files, purpose="vision")

    text_content = message.content
    message.content = []
    if text_content:
        message.content.append({"type": "text", "text": text_content})

    for file_id in file_ids:
        # Keep prior structure so your code doesn't break;
        # we'll translate this into Responses content later.
        message.content.append({"type": "image_file", "image_file": {"file_id": file_id}})


# ---------------------------------------------------------------------
# Responses API
# ---------------------------------------------------------------------
def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    # pydantic v2
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    # pydantic v1
    if hasattr(obj, "dict"):
        return obj.dict()
    # fallback
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"_repr": repr(obj)}


def _extract_text_from_response(resp: Any) -> str:
    d = _as_dict(resp)
    # Many SDKs include "output_text" convenience
    ot = d.get("output_text")
    if isinstance(ot, str) and ot.strip():
        return ot

    out = d.get("output", [])
    parts: List[str] = []
    for item in out if isinstance(out, list) else []:
        it = item if isinstance(item, dict) else _as_dict(item)
        # Common: {"type":"message","content":[{"type":"output_text","text":"..."}]}
        if it.get("type") == "message":
            for c in it.get("content", []) or []:
                cd = c if isinstance(c, dict) else _as_dict(c)
                if cd.get("type") in ("output_text", "text"):
                    t = cd.get("text") or cd.get("value")
                    if t:
                        parts.append(str(t))
    return "".join(parts)


def _extract_tool_calls(resp: Any) -> List[Dict[str, Any]]:
    """
    Returns normalized tool call dicts:
    {
        "id": str,
        "call_id": str,
        "name": str,
        "arguments": dict
    }

    For Responses API, `call_id` is REQUIRED to send back function_call_output.
    """
    d = _as_dict(resp)
    out = d.get("output", [])
    calls: List[Dict[str, Any]] = []

    for item in out if isinstance(out, list) else []:
        it = item if isinstance(item, dict) else _as_dict(item)

        t = it.get("type")

        # ─────────────────────────────────────────────
        # Top-level function/tool call items
        # ─────────────────────────────────────────────
        if t in ("function_call", "tool_call", "output_tool_call", "tool_call_delta"):
            # Prefer call_id (Responses API), fall back to others
            call_id = (
                it.get("call_id")
                or it.get("id")
                or it.get("tool_call_id")
                or it.get("callId")
            )

            name = it.get("name") or (it.get("function") or {}).get("name")

            args_raw = (
                it.get("arguments")
                or (it.get("function") or {}).get("arguments")
            )

            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw) if args_raw.strip() else {}
                except Exception:
                    args = {}
            elif isinstance(args_raw, dict):
                args = args_raw
            else:
                args = {}

            if name:
                calls.append(
                    {
                        "id": call_id or "",
                        "call_id": call_id or "",
                        "name": name,
                        "arguments": args,
                    }
                )

        # ─────────────────────────────────────────────
        # Tool calls nested inside message content
        # ─────────────────────────────────────────────
        if t == "message":
            for c in it.get("content", []) or []:
                cd = c if isinstance(c, dict) else _as_dict(c)

                if cd.get("type") in ("tool_call", "output_tool_call"):
                    call_id = (
                        cd.get("call_id")
                        or cd.get("id")
                        or cd.get("tool_call_id")
                        or cd.get("callId")
                    )

                    name = cd.get("name") or (cd.get("function") or {}).get("name")

                    args_raw = (
                        cd.get("arguments")
                        or (cd.get("function") or {}).get("arguments")
                    )

                    if isinstance(args_raw, str):
                        try:
                            args = json.loads(args_raw) if args_raw.strip() else {}
                        except Exception:
                            args = {}
                    elif isinstance(args_raw, dict):
                        args = args_raw
                    else:
                        args = {}

                    if name:
                        calls.append(
                            {
                                "id": call_id or "",
                                "call_id": call_id or "",
                                "name": name,
                                "arguments": args,
                            }
                        )

    return calls


async def _responses_create(**kwargs) -> Any:
    """
    Async wrapper around Responses create.
    Prefers AsyncOpenAI if it has .responses, else uses sync client in a thread.
    """
    if HAS_ASYNC_RESPONSES:
        return await async_openai_client.responses.create(**kwargs)

    if not HAS_SYNC_RESPONSES:
        raise RuntimeError("Your installed openai SDK does not support Responses API on either async or sync clients.")

    return await asyncio.to_thread(lambda: sync_openai_client.responses.create(**kwargs))


async def _responses_create_streaming_ux_to_chainlit(
    *,
    chainlit_msg: cl.Message,
    response_text: str,
):
    """
    Chainlit streaming UX: stream tokens even if the API call was non-streaming.
    This preserves the *UX* of streaming without depending on SDK stream APIs.
    """
    # Fast, no artificial delay; stream_token is fine for incremental UI updates.
    for ch in response_text:
        await chainlit_msg.stream_token(ch)
    await chainlit_msg.update()


def _to_responses_input(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    For this API deployment:
    - Messages should be plain {role, content: str}
    - Tool continuations use typed items like {"type":"function_call_output", ...}
    """
    out: List[Dict[str, Any]] = []

    for m in conversation:
        # Pass through typed tool items unchanged
        if isinstance(m, dict) and m.get("type") in ("function_call_output", "function_call"):
            out.append(m)
            continue

        role = m.get("role", "user")
        content = m.get("content", "")

        # Convert your possible list-of-parts into a single string
        if isinstance(content, list):
            chunks: List[str] = []
            for p in content:
                if isinstance(p, str):
                    chunks.append(p)
                elif isinstance(p, dict):
                    if p.get("type") == "text":
                        chunks.append(p.get("text", ""))
                    else:
                        # fallback: stringify any other structured part
                        chunks.append(json.dumps(p))
                else:
                    chunks.append(str(p))
            content_str = "\n".join([c for c in chunks if c])
        else:
            content_str = str(content)

        out.append({"role": role, "content": content_str})

    return out


async def run_responses_with_tool_loop(
    *,
    conversation: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    model: str,
    instructions_text: str,
) -> Tuple[Any, str]:
    """
    Responses tool loop using proper continuation:
      - First request: full conversation
      - Tool outputs: sent with previous_response_id=<resp.id>
    """
    # First request uses the whole conversation
    resp = await _responses_create(
        model=model,
        instructions=instructions_text,
        tools=tools,
        input=_to_responses_input(conversation),
    )

    while True:
        tool_calls = _extract_tool_calls(resp)
        if not tool_calls:
            return resp, _extract_text_from_response(resp)

        # Build the next "input" as ONLY function_call_output items
        tool_outputs: List[Dict[str, Any]] = []

        for call in tool_calls:
            name = call["name"]
            args = call.get("arguments", {}) or {}

            if name == "generate_circuit":
                topology = args.get("topology", "")
                dpi = int(args.get("dpi", 300))
                pretty = bool(args.get("pretty", True))
                png_bytes = generate(topology, dpi=dpi, pretty=pretty)
                await send_image_to_canvas(png_bytes)
                output_str = json.dumps(
                    {
                        "status": "ok",
                        "artifact_type": "diagram",
                        "display_target": "interactive_canvas",
                        "note": "Diagram has been rendered and displayed. Continue tutoring using the diagram.",
                    }
                )

            elif name == "generate_latex":
                latex = args.get("latex", "")
                dpi = int(args.get("dpi", 300))
                snippet = bool(args.get("snippet", False))
                png_bytes = generate(latex, dpi=dpi, snippet=snippet)  # type: ignore
                await send_image_to_canvas(png_bytes)
                output_str = json.dumps({"status": "ok", "note": "LaTeX rendered and sent to canvas."})

            else:
                output_str = json.dumps({"status": "error", "error": f"Unknown tool: {name}"})

            call_id = call.get("call_id") or call.get("id")
            if not call_id:
                # Extremely rare, but don’t crash: feed as user-visible text
                tool_outputs.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": f"[Tool output missing call_id] {output_str}"}],
                    }
                )
            else:
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": output_str,
                    }
                )

        # ✅ Continuation request: MUST reference the response that contained the tool call(s)
        resp = await _responses_create(
            model=model,
            instructions=instructions_text,
            tools=tools,
            previous_response_id=getattr(resp, "id", None) or _as_dict(resp).get("id"),
            input=tool_outputs,
        )


# ---------------------------------------------------------------------
# Chainlit lifecycle
# ---------------------------------------------------------------------
@cl.on_chat_start
async def start_chat():
    # Session-local conversation state
    cl.user_session.set("conversation", [])

    # Debug similar to original
    await cl.Message(content=f"DEBUG tools = {[t.get('type') for t in [CODE_INTERPRETER_TOOL, CIRCUIT_TOOL, LATEX_TOOL]]}").send()

    print("Session id:", cl.user_session.get("id"))
    await cl.Message(content=f"Hello, I'm {ASSISTANT_NAME}! Your AI tutor that can draw! What can I help you with?").send()

    # Start drawing app
    global canvas_process
    canvas_process = subprocess.Popen(["python", "interactive_canvas.py", cl.user_session.get("id")])


@cl.on_chat_end
async def end_chat():
    """Terminate the drawing app when chat ends."""
    global canvas_process
    if canvas_process and canvas_process.poll() is None:
        canvas_process.terminate()
        canvas_process.wait()
        canvas_process = None
        print("Interactive canvas closed.")


@cl.on_message
async def main(message: cl.Message):
    # Keep original attachment processing (even if Responses ignores some attachment metadata)
    _ = await process_files(message.elements)
    await append_images_to_message(message)

    conversation: List[Dict[str, Any]] = cl.user_session.get("conversation") or []

    visualize_message = {
        "type": "text",
        "text": "Visualize using Code Interpreter if you think it would be helpful, write math in $ dollar signs $",
    }

    # Add user message to conversation
    # message.content is either a string or list of parts from append_images_to_message
    user_content = message.content
    if isinstance(user_content, str):
        user_content = user_content + "\n\n" + visualize_message["text"]
    elif isinstance(user_content, list):
        user_content = user_content + [visualize_message]
    else:
        user_content = str(user_content) + "\n\n" + visualize_message["text"]

    conversation.append({"role": "user", "content": user_content})

    # Decide active tool set (keep both CIRCUIT_TOOL and LATEX_TOOL available, plus code interpreter)
    tools = [CODE_INTERPRETER_TOOL, CIRCUIT_TOOL, LATEX_TOOL]

    # Run Responses with tool loop
    chainlit_out = await cl.Message(author=ASSISTANT_NAME, content="").send()

    try:
        _, final_text = await run_responses_with_tool_loop(
            conversation=conversation,
            tools=tools,
            model=os.environ.get("OPENAI_MODEL", "gpt-5.2"),
            instructions_text=instructions,
        )
    except Exception as e:
        await chainlit_out.stream_token(f"\n\n[ERROR] {e}")
        await chainlit_out.update()
        raise

    # Stream final text to Chainlit (UX)
    await _responses_create_streaming_ux_to_chainlit(chainlit_msg=chainlit_out, response_text=final_text)

    # Save assistant message to conversation
    conversation.append({"role": "assistant", "content": final_text})
    cl.user_session.set("conversation", conversation)


# Optional: retained helper
async def prompt_geometry_3k_question(question_path: str):
    """Prompts with question from Geometry3k"""
    with open(question_path, "r") as file:
        question = json.load(file)
        prompt = GeoPrompt().initial_prompt(question, n_images=1)
        await cl.Message(content=f"Question:\n{question['annotat_text']}").send()
        message = cl.Message(content=prompt)
        await main(message)
