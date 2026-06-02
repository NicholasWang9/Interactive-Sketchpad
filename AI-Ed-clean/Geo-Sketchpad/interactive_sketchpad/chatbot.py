from openai import AsyncOpenAI
import chainlit as cl
import httpx
import subprocess
import json
from io import BytesIO
from pathlib import Path
from typing import List
from render_latex import generate
import re

# -----------------------------
# OpenAI client
# -----------------------------
async_openai_client = AsyncOpenAI()

# -----------------------------
# Instructions
# -----------------------------

instructions = """
You are a geometry tutor and you are given a bank of geometry problems written in LaTeX. 
Each problem contains:
- A tag at the top describing the concepts covered and the level of difficulty
- A golden example interaction between a tutor (Q) and a student (A) solving the problem

Your primary goal is to guide the student through solving problems by providing small hints from the example interaction in the problem file — not full solutions.

A student will ask you for help practicing a certain geometry topic at a certain difficulty level, and you will give them a problem from one of the given LaTeX files, making sure that the problem you choose has a tag that matches the student's chosen topic and level.
IMPORTANT: On the initial presentation of a new problem, you must present the problem statement first, then render the diagram with generate_latex, and only after the diagram has been rendered may you give the first hint.
Do not mention to the student which file was used.
ALWAYS check that the student's responses are accurate and your solution is correct, following the example.

--- PROBLEM SELECTION ---
Whenever the student asks to practice a specific geometry topic OR requests another problem of the same type, you MUST follow this exact output structure:

1) Select a problem from the bank whose tag matches the requested topic.
2) Respond with the problem statement (text only).
3) Immediately call the generate_latex tool to render the TikZ diagram.
4) After the diagram is rendered, give the first hint from the example interaction.
5) Then stop and wait for the student's response.

You MUST always output all three parts (problem statement + diagram + first hint), but the diagram must come before the first hint.

--- INTERACTION STYLE ---
- You MUST ALWAYS EXACTLY follow each step of the solution in the chosen problem file. You should take on the role of "Q:" in the example interaction.
- Use an interactive approach to engage the student in answering questions to solve this problem STEP by STEP. Make sure to WAIT until student answers your question before continuing.
- Always respond in a brief and concise manner.
- Verify whether the student's response is correct before proceeding.

--- VERIFICATION POLICY (NON-NEGOTIABLE) ---
After every student message:
1. Determine if the student's response is correct or incorrect according to the example interaction.
2. If correct: briefly acknowledge it and proceed with the next step or hint.
3. If incorrect: clearly and gently explain what is wrong, and guide the student to correct it.
4. If the student tries to use a different approach from the given solution, you should gently correct them and steer them back to the example solution and interaction.
5. If the student is correct but doesn't follow the example interaction, you should still say that they are correct, but then steer them back to the example solution and interaction.

IMPORTANT: You should utilize mathematical concepts and operations when verifying correctness against the example interaction. Examples:
- When verifying equality, allow for rearranging the equation. For example, the following equations are all the same: AB/AM = BC/MC, BC/MC = AB/AM, and AM/MC = AB/BC.
- Triangles are the same regardless of vertex order. For example, ABC, CAB, BCA, and BAC are all the same triangle. 
- Lines are the same regardless of vertex order. For example, AB and BA are the same line.

Always verify. Never skip this step.

--- HINTING POLICY ---
- Provide only one hint at a time.
- Do NOT give away the answer.
- Hints should gently guide the student's thinking.
- Hints should come from the "Q:" steps of the example interaction in the problem file.
- On the initial problem presentation, DO NOT give the first hint until AFTER the initial diagram has been rendered and shown.

--- DIAGRAM USAGE ---
- When a problem involves visualization, always include diagrams.
- For the initial problem presentation, render the diagram first, then give the first hint that refers to that diagram.
- latex geometry diagrams: ALWAYS use generate_latex. DO NOT use Code Interpreter for latex geometry diagrams.
- If a similar diagram has already been drawn, reuse or adapt that code rather than starting from scratch.

--- TOOL USE: LATEX GEOMETRY DIAGRAM GENERATION ---
- You have access to a function tool named generate_latex that returns a rendered diagram image.

WHEN TO CALL:
- To render the initial TikZ diagram before the first hint.
- If the user mentions the geometry diagram or adds lines, or you give hints that involve the geometry diagram.

HOW TO CALL:
- Call generate_latex with latex, where latex is a string containing the LaTeX code for the tikz diagram.
- Optional: dpi (default 600), snippet (default true)

--- TOOL CONTINUATION (CRITICAL) ---
Tool calls are internal actions. After any tool completes successfully:
- You MUST immediately continue the conversation in the same run.
- If this is the initial diagram for a new problem, provide the FIRST hint only after the diagram is rendered.
- Otherwise, provide the NEXT hint after the updated diagram is rendered.
- Do NOT give a hint before the corresponding diagram has been rendered.
- Then WAIT for the student's reply.

If the tool fails, briefly explain the failure and ask ONE question to proceed.

--- INTERMEDIATE INTERACTIVE DIAGRAMS (CRITICAL) ---
If the example conversation in the file includes an intermediate interactive diagram at a certain step, you should use the generate_latex tool to render that diagram before giving the corresponding hint.
Additionally, if your hint requires drawing auxiliary lines, extending segments, adding intersection points, marking angles or equal lengths, or modifying the diagram in any way: ALWAYS call generate_latex again to render the updated diagram first, then give the hint.

--- AFTER THE PROBLEM IS SOLVED ---
When the student reaches the correct solution and you reach the end of the example conversation, briefly confirm that the student's result is correct.
Then, ONLY if the file content includes a randomized diagram, ask "Do you want to practice a similar problem with different numbers?".
If they say yes:
- Generate a new problem of the same type, using the EXACT randomized diagram code and problem statement given in the file.
- Follow the full PROBLEM GENERATION PROTOCOL again: problem statement + rendered diagram using generate_latex + first hint.
- The diagram must again come before the first hint.

Otherwise, if the file content does not include a randomized diagram, ask "Do you want to look at another problem in a related topic or choose a different topic to practice?". Then retrieve a new problem file based on the response. 

--- EXAMPLE INTERACTION ---

Student: Asks for a problem

Tutor:
[Problem statement]
[generate_latex → Diagram 1]
[Hint 1 related to Diagram 1]

Student: Responds to hint 1

Tutor:
[generate_latex → Diagram 2 if needed]
[Hint 2 related to Diagram 2]

Student: Responds to hint 2

After solving:
Tutor: Do you want to practice a similar problem with different numbers?

Student: Yes

Tutor:
[Problem statement]
[generate_latex → Diagram 1]
[Hint 1 related to Diagram 1]

You should only give the solution if the student explicitly asks for it.

--- FORMATTING RULES (CRITICAL) ---
ALWAYS write math expressions using $...$ for LaTeX rendering, for example: $\\sin x$.
NEVER use brackets for LaTeX math output.

ALWAYS use generate_latex for any TikZ diagram. Do not use Code Interpreter.

EXTREMELY IMPORTANT:
- ALWAYS follow the example solution given in the problem file EXACTLY.
- ALWAYS follow the diagram code given in the problem file EXACTLY.
- ALWAYS verify that the student's response is correct before proceeding.
"""


LATEX_TOOL = {
    "type": "function",
    "name": "generate_latex",
    "description": (
        "Generate a diagram given a latex document"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "latex": {"type": "string"},
            "dpi": {"type": "integer", "default": 600},
            "snippet": {"type": "boolean", "default": True},
        },
        "required": ["latex"],
    },
}


# -----------------------------
# Canvas integration
# -----------------------------
CANVAS_APP_URL = "http://0.0.0.0:8081/send_image_to_canvas"
# CANVAS_APP_URL = "http://167.172.31.0:8081/send_image_to_canvas"
canvas_process = None


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
    # async with httpx.AsyncClient() as client:
    #    files = {"file": ("generated.png", BytesIO(image_bytes), "image/png")}
    #    response = await client.post(CANVAS_APP_URL, files=files)

    # # Send original (uncropped) to canvas
    # async with httpx.AsyncClient() as client:
    #     files = {"file": ("generated.png", BytesIO(image_bytes), "image/png")}
    #     response = await client.post(CANVAS_APP_URL, files=files)

    # if response.status_code != 200:
    #     print("Failed to send image:", response.text)
    #     return

    # print("Image successfully sent to interactive canvas")

    # Create cropped version ONLY for chat
    cropped_bytes = autocrop_png(image_bytes)

    await cl.Message(
        author="Tutor",
        content="",
        elements=[
            cl.Image(
                name="diagram",
                content=cropped_bytes,
                display="inline",
            )
        ],
    ).send()

# -----------------------------
# File upload helpers
# -----------------------------
async def upload_files(files, purpose="assistants"):
    ids = []
    for f in files:
        uploaded = await async_openai_client.files.create(
            file=Path(f.path),
            purpose=purpose,
        )
        ids.append(uploaded.id)
    return ids

async def append_images_to_message(message: cl.Message):
    image_files = [f for f in message.elements if f.type == "image"]
    if not image_files:
        return

    # Upload images for vision
    file_ids = await upload_files(image_files, purpose="vision")

    content = []

    # Text part
    if message.content:
        content.append({
            "type": "input_text",
            "text": message.content
        })

    # Image parts
    for fid in file_ids:
        content.append({
            "type": "input_image",
            "image_file_id": fid
        })

    message.content = content


# reformats latex in square brackets to use dollar signs.
def correct_latex(text: str) -> str:
    text = re.sub(
        r'\\\[(.*?)\\\]',
        r'$$\1$$',
        text,
        flags=re.DOTALL
    )
    
    # Inline math: \( ... \)  →  $ ... $
    text = re.sub(
        r'\\\((.*?)\\\)',
        r'$\1$',
        text,
        flags=re.DOTALL
    )

    return text

async def select_problem(student_query: str):

    response = await async_openai_client.responses.create(
        model="gpt-5.4",
        tools=[{
            "type": "file_search",
            "vector_store_ids": ["vs_69bafcba7fbc8191b9feffbff2ba1c00"]
        }],
        input=f"""You are a geometry tutor with access to a bank of geometry problems written in LaTeX.

        Each problem file contains:
        - Tags describing the geometry concepts and difficulty level
        - A golden example interaction and solution between a tutor (Q) and a student (A) solving the problem step-by-step
        - Some problem files also contain code for a randomized diagram at the end to generate new problems of the same type

        Student request:
        {student_query}


        Search the vector store and return the most relevant problem with a tag that matches the student's chosen topic and level. 
        Return the FULL FILE CONTENT, including the problem, diagram, the entire example conversation, and randomized diagrams, until you reach the \end{{document}} line. 
        Copy the file content EXACTLY. 
        """
    )
    
    # print(response.output_text)
    return response.output_text

# -----------------------------
# Chat lifecycle
# -----------------------------
@cl.on_chat_start
async def start_chat():
    global canvas_process

    # initialize chosen problem file
    cl.user_session.set("active_problem", None)

    # initialize conversation memory
    cl.user_session.set(
        "history",
        [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": instructions,
                    }
                ],
            }
        ],
    )

    await cl.Message(
        content=("Hello! I'm your AI geometry tutor that can draw. What can I help you with? Here are some sample topics:"
         "\n - Angles (e.g. angle bisector, angle chasing, angles and circles, angles in triangle, vertical angles)"
         "\n - Area (e.g. area of kite, area of rectangle, area optimization, area of triangles, area ratio)"
         "\n - Circles (e.g. circle area, circumradius and inradius, cyclic quadrilateral, tangents)"
         "\n - Congruent triangles"
         "\n - Parallel lines"
         "\n - Polygons (e.g. polygon area, polygon perimeter, polygon sides)"
         "\n - Power of a point"
         "\n - Pythagorean theorem"
         "\n - Rectangles"
         "\n - Similar triangles"
         "\n\nYou can also specify a difficulty level from Basic, Easy, or Medium.")
    ).send()

    canvas_process = subprocess.Popen(
        ["python", "interactive_canvas.py", cl.user_session.get("id")]
    )


@cl.on_chat_end
async def end_chat():
    global canvas_process
    if canvas_process and canvas_process.poll() is None:
        canvas_process.terminate()
        canvas_process.wait()
        canvas_process = None


# -----------------------------
# Main message handler (Responses API)
# -----------------------------
@cl.on_message
async def main(message: cl.Message):
    await append_images_to_message(message)
    history = cl.user_session.get("history")
    active_problem = cl.user_session.get("active_problem")
    user_content = message.content

    if isinstance(user_content, str):
        user_content = [{"type": "input_text", "text": user_content}]

    # Store user message
    history.append(
        {
            "role": "user",
            "content": user_content + [
                {
                    "type": "input_text",
                    "text": "Visualize with diagrams if helpful. Write math in $...$."
                }
            ],
        }
    )

    is_new_problem = active_problem is None

    # -----------------------------
    # Retrieve new problem
    # -----------------------------
    if is_new_problem:
        contents = await select_problem(message.content)
        print("no active problem")
        print(contents)

        cl.user_session.set("active_problem", contents)

        history.append(
            {
                "role": "system",
                "content": f"""The following is the active problem file.
You MUST follow the diagram code and example interaction in the following problem file EXACTLY.
Treat the tutor steps as a script and reveal them one step at a time.

CRITICAL ORDERING RULE:
- On the initial presentation of a new problem, first give the problem statement.
- Then call generate_latex to render the initial diagram.
- Only after the diagram is rendered may you give the first hint.
- Never output the first hint before the initial diagram.
- After any diagram is rendered, continue in a NEW text message.
- Do NOT call generate_latex again unless the diagram actually needs to change.

For later steps, if a diagram update is needed, render the updated diagram before giving the corresponding hint.

----- BEGIN FILE -----
{contents}
----- END FILE -----
"""
            }
        )

    assistant_text = ""

    # This is the currently active streamed text message.
    # After a diagram is sent, we set this to None so future text goes into a new message.
    current_msg = await cl.Message(author="Tutor", content="").send()
    current_visible_text = ""

    initial_diagram_rendered = False

    # Keep running the model until it stops making tool calls
    while True:
        tool_called_this_pass = False
        pass_text = ""
        pass_visible_text = ""

        tool_call = None
        tool_args_buffer = ""

        async with async_openai_client.responses.stream(
            model="gpt-5.4",
            input=history,
            tools=[
                {
                    "type": "code_interpreter",
                    "container": {"type": "auto", "memory_limit": "4g"}
                },
                {
                    "type": "file_search",
                    "vector_store_ids": ["vs_69bafcba7fbc8191b9feffbff2ba1c00"],
                },
                LATEX_TOOL
            ],
            temperature=0,
        ) as stream:

            async for event in stream:
                if event.type == "response.output_text.delta":
                    assistant_text += event.delta
                    pass_text += event.delta
                    pass_visible_text += event.delta

                    # If the previous thing was a diagram, start a fresh text message
                    if current_msg is None:
                        current_msg = await cl.Message(author="Tutor", content="").send()
                        current_visible_text = ""

                    current_visible_text += event.delta
                    await current_msg.stream_token(event.delta)

                elif event.type == "response.output_image":
                    image_id = event.image_id
                    image_bytes = await async_openai_client.files.content(image_id)
                    await send_image_to_canvas(image_bytes)

                    # Any text after this should go into a NEW message
                    current_msg = None
                    current_visible_text = ""

                elif event.type == "response.output_item.added":
                    item = event.item
                    if item.type == "function_call":
                        tool_call = item
                        tool_args_buffer = ""

                elif event.type == "response.function_call_arguments.delta":
                    tool_args_buffer += event.delta

                elif event.type == "response.function_call_arguments.done":
                    tool_called_this_pass = True
                    tool_args = json.loads(tool_args_buffer)

                    if tool_call and tool_call.name == "generate_latex":
                        latex = tool_args["latex"]
                        dpi = int(tool_args.get("dpi", 600))
                        snippet = bool(tool_args.get("snippet", True))

                        try:
                            png_bytes = generate(latex, dpi=dpi, snippet=snippet)
                            await send_image_to_canvas(png_bytes)

                            if is_new_problem and not initial_diagram_rendered:
                                initial_diagram_rendered = True

                            # IMPORTANT:
                            # Preserve assistant text already produced in this pass
                            # so the next pass continues instead of restarting.
                            if pass_text.strip():
                                history.append(
                                    {
                                        "role": "assistant",
                                        "content": [
                                            {
                                                "type": "output_text",
                                                "text": pass_text,
                                            }
                                        ],
                                    }
                                )
                                pass_text = ""
                                pass_visible_text = ""

                            history.append(
                                {
                                    "type": "function_call",
                                    "call_id": tool_call.call_id,
                                    "name": "generate_latex",
                                    "arguments": json.dumps(tool_args)
                                }
                            )

                            history.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": tool_call.call_id,
                                    "output": (
                                        "LaTeX diagram rendered successfully and shown to the student. "
                                        "Continue from exactly where you left off. "
                                        "If this was the initial diagram for a new problem, now provide the first hint. "
                                        "Otherwise, provide the next hint. "
                                        "Write any further text in a new message after the diagram. "
                                        "Do NOT call generate_latex again unless the diagram needs to change."
                                    )
                                }
                            )

                            # IMPORTANT:
                            # Any text after this diagram must go into a NEW message
                            current_msg = None
                            current_visible_text = ""

                            print("sent tool result back to model")

                        except Exception as e:
                            print(e)
                            print(latex)

                            if pass_text.strip():
                                history.append(
                                    {
                                        "role": "assistant",
                                        "content": [
                                            {
                                                "type": "output_text",
                                                "text": pass_text,
                                            }
                                        ],
                                    }
                                )
                                pass_text = ""
                                pass_visible_text = ""

                            history.append(
                                {
                                    "type": "function_call",
                                    "call_id": tool_call.call_id,
                                    "name": "generate_latex",
                                    "arguments": json.dumps(tool_args)
                                }
                            )

                            history.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": tool_call.call_id,
                                    "output": (
                                        f"Error rendering LaTeX diagram: {e}. "
                                        "Generate corrected LaTeX and call generate_latex again. "
                                        "Do not provide the hint until the diagram is successfully rendered."
                                    )
                                }
                            )

                            print("sent tool error back to model")

                    tool_call = None
                    tool_args_buffer = ""

        # If no tool was called, the model is done for this turn
        if not tool_called_this_pass:
            if pass_text.strip():
                history.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": pass_text,
                            }
                        ],
                    }
                )
            break

    # Final cleanup: correct latex in the currently open text message only
    if current_msg is not None:
        current_msg.content = correct_latex(current_msg.content)
        await current_msg.update()


# -----------------------------
# Geometry3k helper (unchanged logic)
# -----------------------------
async def prompt_geometry_3k_question(question_path: str):
    with open(question_path, "r") as f:
        question = json.load(f)

    await cl.Message(
        content=f"Question:\n{question['annotat_text']}"
    ).send()

    await main(cl.Message(content=question["annotat_text"]))
