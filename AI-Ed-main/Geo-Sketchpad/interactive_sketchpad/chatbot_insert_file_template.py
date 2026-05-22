from openai import AsyncOpenAI
import chainlit as cl
import json
import re
from pathlib import Path
from render_latex import generate

# -----------------------------
# OpenAI client
# -----------------------------
async_openai_client = AsyncOpenAI()

# -----------------------------
# Paths
# -----------------------------
PROBLEM_DIR = "./problems"

# -----------------------------
# Tutor instructions
# -----------------------------
TUTOR_INSTRUCTIONS = """
You are a geometry tutor.

Your job is to follow the scripted interaction from the problem file EXACTLY.

Rules:
- Reveal one tutor step at a time.
- Wait for the student to respond before continuing.
- Verify if the student answer is correct.
- If incorrect, guide them toward the correct reasoning.
- Keep responses concise.
- Always use $...$ for math formatting.

If the step contains TikZ code, call the generate_latex tool to render it.
"""

# -----------------------------
# Latex Tool
# -----------------------------
LATEX_TOOL = {
    "type": "function",
    "name": "generate_latex",
    "description": (
        "Render a TikZ diagram"
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
# Helpers
# -----------------------------

def load_problem_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def extract_steps(file_contents: str):
    """
    Extract Q/A interaction steps from problem file.
    """
    pattern = r"(Q:.*?)(?=A:|$)|(A:.*?)(?=Q:|$)"
    matches = re.findall(pattern, file_contents, re.DOTALL)

    steps = []
    for q, a in matches:
        step = q if q else a
        steps.append(step.strip())

    return steps


async def select_problem(student_query: str):

    response = await async_openai_client.responses.create(
        model="gpt-5-mini",
        tools=[{
            "type": "file_search",
            "vector_store_ids": ["vs_69a99a6bec548191be85455f1050066f"]
        }],
        input=f"""
A student wants help practicing geometry.

Student request:
{student_query}

Find the most relevant geometry problem file.

Return ONLY the filename.
"""
    )

    return response.output_text.strip()


# -----------------------------
# Chat start
# -----------------------------
@cl.on_chat_start
async def start():

    cl.user_session.set("history", [
        {
            "role": "system",
            "content": TUTOR_INSTRUCTIONS
        }
    ])

    cl.user_session.set("active_problem", None)
    cl.user_session.set("problem_steps", None)
    cl.user_session.set("step_index", 0)


# -----------------------------
# Main handler
# -----------------------------
@cl.on_message
async def main(message: cl.Message):

    history = cl.user_session.get("history")
    active_problem = cl.user_session.get("active_problem")

    # -----------------------------
    # Retrieve new problem
    # -----------------------------
    if active_problem is None:

        filename = await select_problem(message.content)

        problem_path = f"{PROBLEM_DIR}/{filename}"

        try:
            contents = load_problem_file(problem_path)
        except:
            await cl.Message(
                content="Could not load problem file."
            ).send()
            return

        steps = extract_steps(contents)

        cl.user_session.set("active_problem", problem_path)
        cl.user_session.set("problem_steps", steps)
        cl.user_session.set("step_index", 0)

        history.append({
            "role": "system",
            "content": f"""
The following is the active problem file.

Follow the scripted interaction exactly.

----- BEGIN FILE -----
{contents}
----- END FILE -----
"""
        })

    # -----------------------------
    # Get next step
    # -----------------------------
    steps = cl.user_session.get("problem_steps")
    step_index = cl.user_session.get("step_index")

    if step_index >= len(steps):

        await cl.Message(
            content="Great work! Would you like another problem?"
        ).send()

        cl.user_session.set("active_problem", None)
        return

    next_step = steps[step_index]

    history.append({
        "role": "system",
        "content": f"""
Execute the next scripted tutor step.

Step {step_index + 1}:
{next_step}

Present it naturally to the student.
"""
    })

    # -----------------------------
    # Model call
    # -----------------------------
    msg = cl.Message(content="")
    await msg.send()

    assistant_text = ""

    stream = await async_openai_client.responses.stream(
        model="gpt-5-chat-latest",
        input=history,
        tools=[LATEX_TOOL],
        temperature=0
    )

    async for event in stream:

        if event.type == "response.output_text.delta":
            assistant_text += event.delta
            msg.content = assistant_text
            await msg.update()

        elif event.type == "response.function_call":

            tool_call = event

            args = json.loads(tool_call.arguments)

            latex = args["latex"]
            dpi = args.get("dpi", 300)

            try:
                png = generate(latex, dpi=dpi)

                await cl.Image(
                    content=png,
                    name="diagram"
                ).send()

            except Exception as e:

                await cl.Message(
                    content=f"Diagram rendering error: {e}"
                ).send()

    history.append({
        "role": "assistant",
        "content": assistant_text
    })

    cl.user_session.set("step_index", step_index + 1)


# -----------------------------
# Geometry3k helper
# -----------------------------
async def prompt_geometry_3k_question(question_path: str):

    with open(question_path) as f:
        question = json.load(f)

    await cl.Message(
        content=f"Question:\n{question['annotat_text']}"
    ).send()

    await main(cl.Message(content=question["annotat_text"]))