"""
chatbot.py — Responses API rewrite (no Assistants/Threads/Runs)

This keeps:
- all prompt strings (instructions_old/instructions/instructions_46/instructions_c/instructions_l)
- all tool definitions (code_interpreter + generate_circuit + generate_latex)
- the interactive canvas integration
- Chainlit wiring (chat start/end/message)
- file upload helpers (kept; Responses input wiring is best-effort and backward compatible)

Important compatibility note:
Some environments still expose Responses only on the *sync* OpenAI client.
This file therefore uses the sync client for Responses calls, executed in a thread,
so it works even when AsyncOpenAI().responses is missing.
"""
import asyncio
import json
import os
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sys
import time

import chainlit as cl
import httpx
from chainlit.config import config
from chainlit.element import Element
from dotenv import load_dotenv
from literalai.helper import utc_now
from openai import AsyncOpenAI, OpenAI


# from circuit_generation import generate
# from circuit_ import generate
# from circuit_components import generate # added support for capacitors, inductors, switches
# from circuit_components_2 import generate
from circuit_components_3 import generate
# from render_latex import generate as generate_latex_bytes  # if you have a separate renderer
from geometry_components import generate as generate_geometry

import re

from fastapi import UploadFile, File, HTTPException, Query
from chainlit.server import app as chainlit_app
from types import SimpleNamespace
import tempfile
import uuid

from prompt_circuit import instructions_circuit
from prompt_calculus import instructions_calculus
from prompt_geometry import instructions_geometry


@cl.set_chat_profiles
def chat_profile():
    return [
        cl.ChatProfile(
            name="circuit",
            display_name="Circuit Tutor",
            markdown_description="Tutor for circuits, with series/parallel diagrams.",
        ),
        cl.ChatProfile(
            name="calculus",
            display_name="Calculus Tutor",
            markdown_description="Tutor for calculus problems with graphs and visualizations.",
        ),
        cl.ChatProfile(
            name='geometry',
            display_name="Geometry Tutor",
            markdown_description="Still in progress.",
        )
    ]



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
# Prompts
# ---------------------------------------------------------------------

# Choose which instruction set is active (UNCHANGED behavior)
# instructions = instructions_46
# instructions = instructions_old
instructions = instructions_circuit

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

GEOMETRY_TOOL = {
    "type": "function",
    "name": "generate_geometry",
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


def get_profile_config():
    profile = cl.user_session.get("chat_profile") or "circuit"

    if profile == "calculus":
        return {
            "name": "Calculus Tutor",
            "instructions": instructions_calculus,
            "tools": [CODE_INTERPRETER_TOOL],
        }

    if profile == "geometry":
        return {
            "name": "Geometry Tutor",
            "instructions": instructions_geometry,
            "tools": [GEOMETRY_TOOL]
        }

    return {
        "name": "Circuit Tutor",
        "instructions": instructions_circuit,
        "tools": [CIRCUIT_TOOL],
    }

# Keep UI name consistent with original assistant name
ASSISTANT_NAME = "Interactive Sketchpad"
config.ui.name = ASSISTANT_NAME

# ---------------------------------------------------------------------
# Canvas integration
# ---------------------------------------------------------------------
canvas_process = None
# CANVAS_APP_URL = "http://0.0.0.0:8081/send_image_to_canvas"
CANVAS_APP_URL = "http://127.0.0.1:8081/send_image_to_canvas"
PENDING_CANVAS_UPLOADS: Dict[str, List[str]] = {}


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
    t0 = time.time()

    async with httpx.AsyncClient() as client:
        files = {"file": ("generated.png", BytesIO(image_bytes), "image/png")}
        response = await client.post(CANVAS_APP_URL, files=files)

    print("SEND TO CANVAS HTTP:", time.time() - t0)

    if response.status_code != 200:
        print("Failed to send image:", response.text)
        return

    print("Image successfully sent to interactive canvas")

    # Create cropped version ONLY for chat
    t1 = time.time()
    cropped_bytes = autocrop_png(image_bytes)
    print("AUTOCROP:", time.time() - t1)
    t2 = time.time()

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
    print("SEND TO CHAINLIT:", time.time() - t2)


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

    #final_text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', final_text)

    return text


# ---------------------------------------------------------------------
# Responses API glue
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


def strip_broken_image_markdown(text: str) -> str:
    # Only remove Markdown images: ![alt](url)
    return re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)

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
    chainlit_msg.content = correct_latex(strip_broken_image_markdown(chainlit_msg.content))
    await chainlit_msg.update()


def _to_responses_input(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Responses input builder that preserves multimodal parts.
    - Text -> input_text
    - Uploaded image_file -> input_image (file_id)
    - Keeps tool continuation items unchanged
    """
    out: List[Dict[str, Any]] = []

    for m in conversation:
        # Pass through typed tool items unchanged
        if isinstance(m, dict) and m.get("type") in ("function_call_output", "function_call"):
            out.append(m)
            continue

        role = m.get("role", "user")
        content = m.get("content", "")

        # If content is already a list of parts, map them to Responses parts
        if isinstance(content, list):
            parts: List[Dict[str, Any]] = []
            for p in content:
                if isinstance(p, str):
                    if p.strip():
                        parts.append({"type": "input_text", "text": p})
                    continue

                if isinstance(p, dict):
                    t = p.get("type")
                    if t == "text":
                        txt = p.get("text", "")
                        if txt:
                            parts.append({"type": "input_text", "text": txt})
                    elif t == "image_file":
                        fid = (p.get("image_file") or {}).get("file_id")
                        if fid:
                            parts.append({"type": "input_image", "file_id": fid})
                    else:
                        # fallback: preserve as text so we don't drop info
                        parts.append({"type": "input_text", "text": json.dumps(p)})
                    continue

                # fallback for anything else
                parts.append({"type": "input_text", "text": str(p)})

            out.append({"role": role, "content": parts})
        else:
            out.append({"role": role, "content": str(content)})

    return out

async def handle_response_artifacts(resp: Any):
    """
    Generic handler for artifacts produced by built-in tools,
    especially Code Interpreter images.
    """
    d = _as_dict(resp)

    for item in d.get("output", []) or []:
        item_type = item.get("type")

        # Case 1: direct image output
        if item_type in ("output_image", "image"):
            file_id = item.get("file_id") or item.get("image_id")
            if file_id:
                await _send_openai_file_to_canvas(file_id)

        # Case 2: message content contains image
        for c in item.get("content", []) or []:
            c_type = c.get("type")

            if c_type in ("output_image", "image"):
                file_id = c.get("file_id") or c.get("image_id")
                if file_id:
                    await _send_openai_file_to_canvas(file_id)

            # Case 3: Code Interpreter file annotation
            if c_type in ("output_text", "text"):
                for ann in c.get("annotations", []) or []:
                    file_id = ann.get("file_id")
                    container_id = ann.get("container_id")

                    if file_id and container_id:
                        await _send_container_file_to_canvas(
                            file_id=file_id,
                            container_id=container_id,
                        )
                    elif file_id:
                        await _send_openai_file_to_canvas(file_id)

def already_sent_artifact(key: str) -> bool:
    sent = cl.user_session.get("sent_artifact_ids")
    if sent is None:
        sent = set()

    if key in sent:
        cl.user_session.set("sent_artifact_ids", sent)
        return True

    sent.add(key)
    cl.user_session.set("sent_artifact_ids", sent)
    return False


async def _send_openai_file_to_canvas(file_id: str):
    key = f"openai:{file_id}"
    if already_sent_artifact(key):
        return

    try:
        file_resp = await async_openai_client.files.content(file_id)
        image_bytes = file_resp.read()
        print(f"Sending OpenAI artifact to canvas: {file_id}")
        await send_image_to_canvas(image_bytes)
    except Exception as e:
        print(f"Failed to send OpenAI file artifact {file_id}: {e}")


async def _send_container_file_to_canvas(file_id: str, container_id: str):
    key = f"container:{container_id}:{file_id}"
    if already_sent_artifact(key):
        return

    try:
        file_resp = await async_openai_client.containers.files.content.retrieve(
            file_id=file_id,
            container_id=container_id,
        )
        image_bytes = file_resp.read()
        print(f"Sending container artifact to canvas: {file_id}")
        await send_image_to_canvas(image_bytes)
    except Exception as e:
        print(f"Failed to send container artifact {file_id}: {e}")



async def run_responses_with_tool_loop(
    *,
    conversation: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    model: str,
    instructions_text: str,
) -> Tuple[Any, str]:
    """
    Responses tool loop with single-tool interleaving:
      - First request: full conversation
      - Continuations: previous_response_id + function_call_output
      - IMPORTANT: executes only ONE tool call per cycle so the model can do:
            diagram -> text -> diagram -> text
        instead of batching diagrams first.
    """
    t0 = time.time()
    resp = await _responses_create(
        model=model,
        instructions=instructions_text,
        tools=tools,
        input=_to_responses_input(conversation),
        parallel_tool_calls=False,  # avoid multi-tool batching
    )
    print("RESPONSES CREATE:", time.time() - t0)
    t1 = time.time()
    await handle_response_artifacts(resp)
    print("ARTIFACT HANDLING:", time.time() - t1)

    while True:
        tool_calls = _extract_tool_calls(resp)

        # If the model produced any visible text, return it now instead of
        # continuing to drain future tool calls.
        text = _extract_text_from_response(resp)
        if text and text.strip():
            return resp, text

        if not tool_calls:
            return resp, text

        # Execute ONLY the first tool call, then immediately continue.
        call = tool_calls[0]
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
                    "note": "Diagram rendered. Continue with exactly one tutoring step that references this diagram.",
                }
            )

        elif name == "generate_geometry":
            description = args.get("topology", "")
            dpi = int(args.get("dpi", 300))
            pretty = bool(args.get("pretty", True))
            print(description)

            # Placeholder for now: render a simple text-based placeholder image.
            png_bytes = generate_geometry(description, dpi=dpi, pretty=pretty,)

            await send_image_to_canvas(png_bytes)

            output_str = json.dumps(
                {
                    "status": "ok",
                    "artifact_type": "geometry_diagram",
                    "display_target": "interactive_canvas",
                    "note": "Geometry placeholder rendered. Continue with exactly one tutoring step that references this diagram.",
                }
            )

        elif name == "generate_latex":
            latex = args.get("latex", "")
            dpi = int(args.get("dpi", 300))
            snippet = bool(args.get("snippet", False))
            png_bytes = generate(latex, dpi=dpi, snippet=snippet)  # type: ignore
            await send_image_to_canvas(png_bytes)
            output_str = json.dumps(
                {
                    "status": "ok",
                    "artifact_type": "latex",
                    "display_target": "interactive_canvas",
                    "note": "LaTeX rendered. Continue with exactly one tutoring step.",
                }
            )

        else:
            output_str = json.dumps(
                {"status": "error", "error": f"Unknown tool: {name}"}
            )

        call_id = call.get("call_id") or call.get("id")
        if not call_id:
            tool_outputs = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"[Tool output missing call_id] {output_str}",
                        }
                    ],
                }
            ]
        else:
            tool_outputs = [
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output_str,
                }
            ]

        resp = await _responses_create(
            model=model,
            instructions=instructions_text,
            tools=tools,
            previous_response_id=getattr(resp, "id", None) or _as_dict(resp).get("id"),
            input=tool_outputs,
            parallel_tool_calls=False,
        )
        await handle_response_artifacts(resp)


# ---------------------------------------------------------------------
# Chainlit lifecycle
# ---------------------------------------------------------------------
@chainlit_app.post("/upload")
async def upload_canvas_image(
    file: UploadFile = File(...),
    session: str = Query(default=None),
    session_id: str = Query(default=None),
):
    """
    Receives a drawing from interactive_canvas.py and stores it so the next
    chat message from that session includes the image.
    Accepts either ?session=... or ?session_id=...
    """
    actual_session = session or session_id
    if not actual_session:
        raise HTTPException(status_code=400, detail="missing session/session_id")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty upload")
    content = autocrop_png(content)

    tmp_dir = Path(tempfile.gettempdir()) / "interactive_sketchpad_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    out_path = tmp_dir / f"{actual_session}_{uuid.uuid4().hex}.png"
    out_path.write_bytes(content)

    PENDING_CANVAS_UPLOADS.setdefault(actual_session, []).append(str(out_path))
    return {"status": "ok", "session": actual_session, "stored": str(out_path)}


@cl.on_chat_start
async def start_chat():
    cfg = get_profile_config()

    cl.user_session.set("conversation", [])
    cl.user_session.set("active_tutor", cfg["name"])
    cl.user_session.set("sent_artifact_ids", set())

    await cl.Message(
        content=f"Hello, I'm your {cfg['name']}! What can I help you with?"
    ).send()

    global canvas_process
    canvas_process = subprocess.Popen(
        [sys.executable, "interactive_canvas.py", cl.user_session.get("id")]
    )


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
    session_id = cl.user_session.get("id")
    pending_paths = PENDING_CANVAS_UPLOADS.pop(session_id, [])

    if pending_paths:
        for p in pending_paths:
            await cl.Message(
                author="You",
                content="",
                elements=[
                    cl.Image(
                        name=Path(p).name,
                        path=p,
                        display="inline",
                    )
                ],
            ).send()
        
        if message.elements is None:
            message.elements = []

        for p in pending_paths:
            message.elements.append(
                SimpleNamespace(
                    type="image",
                    path=p,
                    name=Path(p).name,
                )
            )
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
    # tools = [CODE_INTERPRETER_TOOL, CIRCUIT_TOOL, LATEX_TOOL]
    cfg = get_profile_config()
    tools = cfg["tools"]

    # Run Responses with tool loop
    chainlit_out = await cl.Message(author=ASSISTANT_NAME, content="").send()

    try:
        _, final_text = await run_responses_with_tool_loop(
            conversation=conversation,
            tools=tools,
            model=os.environ.get("OPENAI_MODEL", "gpt-5.5"),
            instructions_text=cfg["instructions"],
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


