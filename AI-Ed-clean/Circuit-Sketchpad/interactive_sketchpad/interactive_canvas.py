#!/usr/bin/env python3
import os
import sys
import threading
from io import BytesIO
from typing import Dict, List, Tuple

import httpx
import uvicorn
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from PIL import Image

# Usage:
#   python interactive_canvas.py <SESSION_ID>
SESSION_ID = sys.argv[1] if len(sys.argv) > 1 else "default"

# Where user drawings should be forwarded.
# CHATBOT_UPLOAD_URL = os.environ.get("CHATBOT_UPLOAD_URL", "http://127.0.0.1:8000/upload")
CHATBOT_UPLOAD_URL = os.environ.get("CHATBOT_UPLOAD_URL", "http://18.27.78.35:8001/upload")

# Chat UI to embed alongside the canvas (the Chainlit app).
# CHAT_UI_URL = os.environ.get("CHAT_UI_URL", "http://127.0.0.1:8000/interactive_sketchpad")
CHAT_UI_URL = os.environ.get("CHAT_UI_URL", "http://18.27.78.35:8001/interactive_sketchpad")

app = FastAPI()

# In-memory history per session_id:
#   history[session_id] = ([png_bytes0, png_bytes1, ...], cursor_index)
_history: Dict[str, Tuple[List[bytes], int]] = {}
_lock = threading.Lock()

# The most recently started chat session. The chat frontend generates a new
# session id on every page load (no cross-reload persistence), so rather
# than binding this server to one session for its whole lifetime, the
# chatbot notifies us of the current session on every chat start, and the
# whiteboard page (below) polls for it and follows along automatically.
_latest_session: str = SESSION_ID

# Optional: cap history to avoid memory blowups
MAX_HISTORY = 200


def _get_state(session_id: str) -> Tuple[List[bytes], int]:
    with _lock:
        if session_id not in _history:
            _history[session_id] = ([], -1)
        return _history[session_id]


def _set_state(session_id: str, imgs: List[bytes], idx: int) -> None:
    with _lock:
        _history[session_id] = (imgs, idx)


def _push_image(session_id: str, png: bytes) -> int:
    """
    Append image to history, truncating any 'forward' entries if user had gone back.
    Returns new cursor index.
    """
    imgs, idx = _get_state(session_id)

    # If we're not at the end, drop forward history
    if 0 <= idx < len(imgs) - 1:
        imgs = imgs[: idx + 1]

    imgs.append(png)

    # Enforce cap
    if len(imgs) > MAX_HISTORY:
        overflow = len(imgs) - MAX_HISTORY
        imgs = imgs[overflow:]
        idx = max(-1, idx - overflow)

    idx = len(imgs) - 1
    _set_state(session_id, imgs, idx)
    return idx


def _move_cursor(session_id: str, delta: int) -> int:
    imgs, idx = _get_state(session_id)
    if not imgs:
        return -1
    idx = max(0, min(len(imgs) - 1, idx + delta))
    _set_state(session_id, imgs, idx)
    return idx


def _set_cursor(session_id: str, new_idx: int) -> int:
    imgs, idx = _get_state(session_id)
    if not imgs:
        return -1
    new_idx = max(0, min(len(imgs) - 1, new_idx))
    _set_state(session_id, imgs, new_idx)
    return new_idx


@app.get("/", response_class=HTMLResponse)
def home(session: str = Query(default=SESSION_ID)):
    return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>Interactive Sketchpad Canvas (Web)</title>
    <style>
      :root {{
        color-scheme: light;
      }}
      html, body {{
        height: 100%;
      }}
      body {{
        font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        margin: 0;
        background: #fff;
        color: #111;
      }}
      /* Explicit dark mode, toggled by the button below (not tied to OS
         preference) -- defaults to light on every fresh load. */
      body.dark {{ background: #121212; color: #e6e6e6; }}
      body.dark .chat-pane, body.dark .canvas-wrap {{ border-color: #444; }}
      body.dark .meta {{ color: #9a9a9a; }}
      body.dark code {{ background: #2a2a2a; color: #e6e6e6; }}
      /* Diagrams render on a white page -- keep the canvas a light grey
         instead of pure white in dark mode, rather than pure black/white clash. */
      body.dark .canvas-wrap {{ background: #ddd; }}
      .app-layout {{
        display: flex;
        gap: 12px;
        align-items: stretch;
        height: 100vh;
        box-sizing: border-box;
        padding: 16px;
      }}
      .pane {{
        display: flex;
        flex-direction: column;
        min-width: 0;
        min-height: 0;
      }}
      .pane-header {{
        font-weight: 600;
        margin-bottom: 8px;
        flex: 0 0 auto;
      }}
      .chat-pane {{
        flex: 1 1 50%;
        min-width: 0;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        box-sizing: border-box;
      }}
      .chat-pane iframe {{
        flex: 1 1 auto;
        width: 100%;
        border: 0;
        border-radius: 4px;
      }}
      .canvas-pane {{
        flex: 1 1 50%;
        min-width: 0;
        overflow: auto;
      }}
      @media (max-width: 1000px) {{
        .app-layout {{
          flex-direction: column;
          height: auto;
        }}
        .chat-pane {{
          flex: 0 0 480px;
        }}
      }}
      .meta {{ color: #666; margin: 8px 0; }}
      .bar {{
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
        margin: 12px 0;
      }}
      button {{ padding: 6px 10px; cursor: pointer; }}
      .tool-btn.active {{ background: #d62828; border-color: #d62828; }}
      #sendDrawing {{
        background: #2e7d32;
        color: #fff;
        border: none;
        font-weight: 600;
        padding: 8px 16px;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
      }}
      #sendDrawing:hover {{ background: #256428; }}
      #sendDrawing:disabled {{ background: #9e9e9e; box-shadow: none; cursor: default; }}
      input[type="range"] {{ width: 320px; }}
      input[type="color"] {{ width: 42px; height: 36px; padding: 0; border: none; background: transparent; }}
      input[type="number"] {{ width: 70px; }}
      code {{ background: #f6f6f6; padding: 2px 4px; border-radius: 4px; }}
      .canvas-wrap {{
        position: relative;
        display: inline-block;
        border: 1px solid #ddd;
        max-width: 95vw;
        max-height: 85vh;
        overflow: auto;
        background: #fff;
      }}
      .canvas-text-input {{
        position: absolute;
        z-index: 5;
        border: 1px dashed #888;
        background: rgba(255, 255, 255, 0.85);
        font-size: 14px;
        padding: 2px 4px;
        min-width: 60px;
      }}
      #baseImg {{
        display: block;
        max-width: 95vw;
        max-height: 85vh;
        user-select: none;
        -webkit-user-drag: none;
      }}
      #drawCanvas, #shapesCanvas {{
        position: absolute;
        inset: 0;
        touch-action: none;
      }}
      #drawCanvas {{
        pointer-events: none;
      }}
      .sep {{ color: #bbb; }}
    </style>
  </head>
  <body>
    <div class="app-layout">
      <aside class="pane chat-pane">
        <div class="pane-header">Chat</div>
        <iframe id="chatFrame" src="{CHAT_UI_URL}" title="Tutor chat"></iframe>
      </aside>

      <main class="pane canvas-pane">
        <div class="pane-header">Canvas</div>
        <div class="meta">Session: <code id="sess">{session}</code></div>

        <div class="canvas-wrap" id="canvasWrap">
          <img id="baseImg" src="/image.png?session={session}&ts=0" alt="No image yet" draggable="false" />
          <canvas id="drawCanvas"></canvas>
          <canvas id="shapesCanvas"></canvas>
        </div>

        <div class="bar">
          <button id="back">◀ Back</button>
          <button id="fwd">Forward ▶</button>

          <span class="meta">Index:</span>
          <span id="idx" class="meta">-</span>
          <span class="meta">/</span>
          <span id="total" class="meta">-</span>

          <input id="slider" type="range" min="0" max="0" value="0" step="1" />

          <label class="meta">
            <input id="follow" type="checkbox" checked />
            Follow latest
          </label>

          <span id="status" class="meta"></span>
        </div>

        <div class="bar">
          <strong>Drawing</strong>
          <button id="toggleDraw">Disable drawing</button>
          <span class="sep">|</span>
          <button id="toolPen" class="tool-btn">Pen</button>
          <button id="toolLine" class="tool-btn">Line</button>
          <button id="toolCircle" class="tool-btn">Circle</button>
          <button id="toolText" class="tool-btn">Text</button>
          <button id="toolShade" class="tool-btn">Shade</button>
          <button id="toolEraser" class="tool-btn">Eraser</button>
          <button id="toolMove" class="tool-btn">Move</button>
          <span class="sep">|</span>
          <label class="meta">Color <input id="colorPicker" type="color" value="#d62828" /></label>
          <label class="meta"><span id="brushLabel">Brush</span> <input id="brushSize" type="number" min="1" max="64" step="1" value="4" /></label>
          <button id="undoStroke">Undo</button>
          <button id="clearDrawing">Clear drawing</button>
          <span class="sep">|</span>
          <button id="sendDrawing">Send image back to tutor</button>
        </div>

        <div class="meta">
          Shortcuts: <code>←</code>/<code>→</code> for back/forward, <code>f</code> toggles follow-latest.
          Hold mouse and drag to draw.
        </div>
      </main>
    </div>

    <script>
      let sessionId = "{session}";
      const sessEl = document.getElementById("sess");
      const chatFrame = document.getElementById("chatFrame");
      const img = document.getElementById("baseImg");
      const canvas = document.getElementById("drawCanvas");
      const shapesCanvas = document.getElementById("shapesCanvas");
      const wrap = document.getElementById("canvasWrap");
      const ctx = canvas.getContext("2d");
      const shapesCtx = shapesCanvas.getContext("2d");
      const idxEl = document.getElementById("idx");
      const totalEl = document.getElementById("total");
      const statusEl = document.getElementById("status");
      const slider = document.getElementById("slider");
      const follow = document.getElementById("follow");
      const colorPicker = document.getElementById("colorPicker");
      const brushSize = document.getElementById("brushSize");
      const toggleDrawBtn = document.getElementById("toggleDraw");
      const brushLabel = document.getElementById("brushLabel");
      const undoStrokeBtn = document.getElementById("undoStroke");
      const clearDrawingBtn = document.getElementById("clearDrawing");
      const sendDrawingBtn = document.getElementById("sendDrawing");
      const toolButtons = {{
        pen: document.getElementById("toolPen"),
        line: document.getElementById("toolLine"),
        circle: document.getElementById("toolCircle"),
        text: document.getElementById("toolText"),
        shade: document.getElementById("toolShade"),
        eraser: document.getElementById("toolEraser"),
        move: document.getElementById("toolMove"),
      }};

      let drawingEnabled = true;
      let currentTool = "pen"; // "pen" | "line" | "circle" | "text" | "shade" | "eraser" | "move"
      let isDrawing = false;
      let lastX = 0;
      let lastY = 0;
      let shapeStartX = 0;
      let shapeStartY = 0;
      let lastTotal = -1;
      let strokeSnapshots = [];

      // Line/circle/text are kept as retained shape objects (not baked
      // pixels) on their own canvas layer, so they can be moved after being
      // placed. Pen, eraser, and shading stay purely raster on `canvas`.
      let shapes = [];
      let nextShapeId = 1;
      let draggingShapeId = null;
      let dragLastX = 0;
      let dragLastY = 0;

      function setStatus(t, ms = 1200) {{
        statusEl.textContent = t || "";
        if (t) setTimeout(() => {{ if (statusEl.textContent === t) statusEl.textContent = ""; }}, ms);
      }}

      function resizeDrawingCanvas(preserveDrawing = true) {{
        const rect = img.getBoundingClientRect();
        if (!rect.width || !rect.height) return;

        const oldWidth = canvas.width;
        const oldHeight = canvas.height;
        const newWidth = Math.round(rect.width);
        const newHeight = Math.round(rect.height);

        const snapshot = preserveDrawing ? canvas.toDataURL("image/png") : null;

        canvas.width = newWidth;
        canvas.height = newHeight;
        canvas.style.width = `${{newWidth}}px`;
        canvas.style.height = `${{newHeight}}px`;
        shapesCanvas.width = newWidth;
        shapesCanvas.height = newHeight;
        shapesCanvas.style.width = `${{newWidth}}px`;
        shapesCanvas.style.height = `${{newHeight}}px`;

        if (!preserveDrawing) {{
          shapes = [];
          redrawShapesCanvas();
        }} else if (oldWidth && oldHeight && (oldWidth !== newWidth || oldHeight !== newHeight)) {{
          // Rescale shapes proportionally, matching how the raster layer
          // below stretches its preserved snapshot to the new size.
          const scaleX = newWidth / oldWidth;
          const scaleY = newHeight / oldHeight;
          for (const s of shapes) {{
            if (s.type === "line") {{
              s.x1 *= scaleX; s.y1 *= scaleY; s.x2 *= scaleX; s.y2 *= scaleY;
            }} else if (s.type === "circle") {{
              s.cx *= scaleX; s.cy *= scaleY; s.r *= (scaleX + scaleY) / 2;
            }} else if (s.type === "text") {{
              s.x *= scaleX; s.y *= scaleY;
            }}
          }}
          redrawShapesCanvas();
        }} else {{
          redrawShapesCanvas();
        }}

        if (!snapshot) return;

        const restore = new Image();
        restore.onload = () => {{
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(restore, 0, 0, canvas.width, canvas.height);
        }};
        restore.src = snapshot;
      }}

      function pointerPos(evt) {{
        const rect = shapesCanvas.getBoundingClientRect();
        return {{
          x: evt.clientX - rect.left,
          y: evt.clientY - rect.top,
        }};
      }}

      function redrawShapesCanvas() {{
        shapesCtx.clearRect(0, 0, shapesCanvas.width, shapesCanvas.height);
        for (const s of shapes) {{
          shapesCtx.save();
          shapesCtx.strokeStyle = s.color;
          shapesCtx.fillStyle = s.color;
          shapesCtx.lineWidth = s.width || 4;
          shapesCtx.lineCap = "round";
          shapesCtx.lineJoin = "round";
          if (s.type === "line") {{
            shapesCtx.beginPath();
            shapesCtx.moveTo(s.x1, s.y1);
            shapesCtx.lineTo(s.x2, s.y2);
            shapesCtx.stroke();
          }} else if (s.type === "circle") {{
            shapesCtx.beginPath();
            shapesCtx.arc(s.cx, s.cy, s.r, 0, Math.PI * 2);
            shapesCtx.stroke();
          }} else if (s.type === "text") {{
            shapesCtx.font = `${{s.fontSize}}px sans-serif`;
            shapesCtx.textBaseline = "top";
            shapesCtx.fillText(s.text, s.x, s.y);
          }}
          shapesCtx.restore();
        }}
      }}

      function distToSegment(px, py, x1, y1, x2, y2) {{
        const dx = x2 - x1, dy = y2 - y1;
        const lenSq = dx * dx + dy * dy;
        let t = lenSq ? ((px - x1) * dx + (py - y1) * dy) / lenSq : 0;
        t = Math.max(0, Math.min(1, t));
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
      }}

      function hitTestShape(x, y) {{
        const tolerance = 8;
        for (let i = shapes.length - 1; i >= 0; i--) {{
          const s = shapes[i];
          if (s.type === "line") {{
            if (distToSegment(x, y, s.x1, s.y1, s.x2, s.y2) <= (s.width || 4) / 2 + tolerance) return s.id;
          }} else if (s.type === "circle") {{
            if (Math.hypot(x - s.cx, y - s.cy) <= s.r + tolerance) return s.id;
          }} else if (s.type === "text") {{
            shapesCtx.font = `${{s.fontSize}}px sans-serif`;
            const w = shapesCtx.measureText(s.text).width;
            if (x >= s.x - tolerance && x <= s.x + w + tolerance && y >= s.y - tolerance && y <= s.y + s.fontSize + tolerance) return s.id;
          }}
        }}
        return null;
      }}

      function moveShapeBy(id, dx, dy) {{
        const s = shapes.find((sh) => sh.id === id);
        if (!s) return;
        if (s.type === "line") {{
          s.x1 += dx; s.y1 += dy; s.x2 += dx; s.y2 += dy;
        }} else if (s.type === "circle") {{
          s.cx += dx; s.cy += dy;
        }} else if (s.type === "text") {{
          s.x += dx; s.y += dy;
        }}
      }}

      function saveStrokeSnapshot() {{
        strokeSnapshots.push({{
          raster: canvas.toDataURL("image/png"),
          shapes: JSON.parse(JSON.stringify(shapes)),
        }});
        if (strokeSnapshots.length > 200) strokeSnapshots.shift();
      }}

      function restoreSnapshot(snapshot) {{
        shapes = snapshot.shapes;
        redrawShapesCanvas();
        const im = new Image();
        im.onload = () => {{
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(im, 0, 0, canvas.width, canvas.height);
        }};
        im.src = snapshot.raster;
      }}

      const toolCursors = {{
        pen: "crosshair",
        line: "crosshair",
        circle: "crosshair",
        text: "text",
        shade: "pointer",
        eraser: "cell",
        move: "grab",
      }};

      function updateActiveToolColor() {{
        const btn = toolButtons[currentTool];
        if (!btn) return;
        const color = colorPicker.value;
        btn.style.backgroundColor = color;
        btn.style.borderColor = color;
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        btn.style.color = luminance > 0.6 ? "#000" : "#fff";
      }}

      function setTool(tool) {{
        currentTool = tool;
        for (const [name, btn] of Object.entries(toolButtons)) {{
          const isActive = name === tool;
          btn.classList.toggle("active", isActive);
          if (!isActive) {{
            btn.style.backgroundColor = "";
            btn.style.borderColor = "";
            btn.style.color = "";
          }}
        }}
        updateActiveToolColor();
        setDrawModeLabel();
      }}

      function setDrawModeLabel() {{
        toggleDrawBtn.textContent = drawingEnabled ? "Disable drawing" : "Enable drawing";
        brushLabel.textContent = currentTool === "eraser" ? "Eraser size" : "Brush size";
        shapesCanvas.style.pointerEvents = drawingEnabled ? "auto" : "none";
        shapesCanvas.style.cursor = drawingEnabled ? (toolCursors[currentTool] || "crosshair") : "default";
      }}

      // Chainlit is the source of truth for light/dark (its own sun-icon
      // switcher, defaulting to light) -- the chat iframe's custom_js relays
      // that choice here via postMessage, so both panes always match. No
      // separate control on the whiteboard side.
      function setTheme(dark) {{
        document.body.classList.toggle("dark", dark);
        document.documentElement.style.colorScheme = dark ? "dark" : "light";
      }}
      window.addEventListener("message", (e) => {{
        if (e.source === chatFrame.contentWindow && e.data && e.data.type === "sketchpad-theme") {{
          setTheme(!!e.data.dark);
        }}
      }});

      function drawFreehandSegment(p) {{
        ctx.save();
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.lineWidth = Math.max(1, parseInt(brushSize.value || "4", 10));

        if (currentTool === "eraser") {{
          ctx.globalCompositeOperation = "destination-out";
          ctx.strokeStyle = "rgba(0,0,0,1)";
        }} else {{
          ctx.globalCompositeOperation = "source-over";
          ctx.strokeStyle = colorPicker.value;
        }}

        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
        ctx.restore();

        lastX = p.x;
        lastY = p.y;
      }}

      function strokeShapePreview(drawFn) {{
        shapesCtx.save();
        shapesCtx.lineCap = "round";
        shapesCtx.lineJoin = "round";
        shapesCtx.lineWidth = Math.max(1, parseInt(brushSize.value || "4", 10));
        shapesCtx.strokeStyle = colorPicker.value;
        drawFn();
        shapesCtx.restore();
      }}

      function hexToRgb(hex) {{
        const clean = hex.replace("#", "");
        const num = parseInt(clean, 16);
        return {{ r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 }};
      }}

      function placeTextInput(x, y) {{
        const input = document.createElement("input");
        input.type = "text";
        input.className = "canvas-text-input";
        input.style.left = `${{x}}px`;
        input.style.top = `${{y}}px`;
        input.style.color = colorPicker.value;
        wrap.appendChild(input);
        input.focus();

        function commit() {{
          const value = input.value;
          if (value) {{
            saveStrokeSnapshot();
            const fontSize = Math.max(12, parseInt(brushSize.value || "4", 10) * 5);
            shapes.push({{ id: nextShapeId++, type: "text", x, y, text: value, color: colorPicker.value, fontSize }});
            redrawShapesCanvas();
          }}
          input.remove();
        }}

        input.addEventListener("keydown", (e) => {{
          if (e.key === "Enter") {{ e.preventDefault(); commit(); }}
          if (e.key === "Escape") {{ e.preventDefault(); input.remove(); }}
        }});
        input.addEventListener("blur", commit);
      }}

      function shadeRegionAt(x, y) {{
        const w = canvas.width, h = canvas.height;
        const cx = Math.round(x), cy = Math.round(y);
        if (cx < 0 || cy < 0 || cx >= w || cy >= h) return;

        // Fill against a composite of the diagram image + current drawing
        // (both raster strokes and placed shapes), so the region's boundary
        // can come from any of them -- but paint the result onto the raster
        // drawing layer only, leaving the diagram and shapes untouched.
        const composite = document.createElement("canvas");
        composite.width = w;
        composite.height = h;
        const cctx = composite.getContext("2d");
        cctx.drawImage(img, 0, 0, w, h);
        cctx.drawImage(canvas, 0, 0, w, h);
        cctx.drawImage(shapesCanvas, 0, 0, w, h);
        const src = cctx.getImageData(0, 0, w, h).data;

        const startIdx = (cy * w + cx) * 4;
        const startR = src[startIdx], startG = src[startIdx + 1], startB = src[startIdx + 2], startA = src[startIdx + 3];
        const tolerance = 40;

        function matches(idx) {{
          const dr = src[idx] - startR, dg = src[idx + 1] - startG, db = src[idx + 2] - startB, da = src[idx + 3] - startA;
          return (dr * dr + dg * dg + db * db + da * da) <= tolerance * tolerance;
        }}

        const visited = new Uint8Array(w * h);
        const stack = [[cx, cy]];
        visited[cy * w + cx] = 1;
        const maxFillPixels = Math.floor(w * h * 0.9);
        let filledCount = 0;

        while (stack.length) {{
          const [px, py] = stack.pop();
          filledCount++;
          if (filledCount > maxFillPixels) {{
            setStatus("Region isn't closed -- couldn't shade it", 2000);
            return;
          }}
          const neighbors = [[px + 1, py], [px - 1, py], [px, py + 1], [px, py - 1]];
          for (const [nx, ny] of neighbors) {{
            if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
            const vIdx = ny * w + nx;
            if (visited[vIdx]) continue;
            if (!matches(vIdx * 4)) continue;
            visited[vIdx] = 1;
            stack.push([nx, ny]);
          }}
        }}

        const fillCanvas = document.createElement("canvas");
        fillCanvas.width = w;
        fillCanvas.height = h;
        const fctx = fillCanvas.getContext("2d");
        const fillImageData = fctx.createImageData(w, h);
        const color = hexToRgb(colorPicker.value);
        const alpha = 130; // partial opacity so lines/labels underneath stay visible
        for (let i = 0; i < visited.length; i++) {{
          if (!visited[i]) continue;
          const idx = i * 4;
          fillImageData.data[idx] = color.r;
          fillImageData.data[idx + 1] = color.g;
          fillImageData.data[idx + 2] = color.b;
          fillImageData.data[idx + 3] = alpha;
        }}
        fctx.putImageData(fillImageData, 0, 0);
        ctx.drawImage(fillCanvas, 0, 0);
      }}

      function eraseShapesAt(x, y) {{
        const id = hitTestShape(x, y);
        if (id == null) return;
        shapes = shapes.filter((s) => s.id !== id);
        redrawShapesCanvas();
      }}

      function onPointerDown(evt) {{
        if (!drawingEnabled) return;
        evt.preventDefault();
        const p = pointerPos(evt);

        if (currentTool === "pen" || currentTool === "eraser") {{
          saveStrokeSnapshot();
          isDrawing = true;
          lastX = p.x;
          lastY = p.y;
          if (currentTool === "eraser") eraseShapesAt(p.x, p.y);
        }} else if (currentTool === "line" || currentTool === "circle") {{
          saveStrokeSnapshot();
          isDrawing = true;
          shapeStartX = p.x;
          shapeStartY = p.y;
        }} else if (currentTool === "text") {{
          placeTextInput(p.x, p.y);
        }} else if (currentTool === "shade") {{
          saveStrokeSnapshot();
          shadeRegionAt(p.x, p.y);
        }} else if (currentTool === "move") {{
          const id = hitTestShape(p.x, p.y);
          if (id != null) {{
            saveStrokeSnapshot();
            draggingShapeId = id;
            dragLastX = p.x;
            dragLastY = p.y;
            // Bring the grabbed shape to the front so it draws on top while dragging.
            const idx = shapes.findIndex((s) => s.id === id);
            const [s] = shapes.splice(idx, 1);
            shapes.push(s);
            redrawShapesCanvas();
          }}
        }}
      }}

      function onPointerMove(evt) {{
        if (!drawingEnabled) return;
        const p = pointerPos(evt);

        if (currentTool === "move") {{
          if (draggingShapeId == null) return;
          evt.preventDefault();
          moveShapeBy(draggingShapeId, p.x - dragLastX, p.y - dragLastY);
          dragLastX = p.x;
          dragLastY = p.y;
          redrawShapesCanvas();
          return;
        }}

        if (!isDrawing) return;
        evt.preventDefault();

        if (currentTool === "pen" || currentTool === "eraser") {{
          drawFreehandSegment(p);
          if (currentTool === "eraser") eraseShapesAt(p.x, p.y);
        }} else if (currentTool === "line") {{
          redrawShapesCanvas();
          strokeShapePreview(() => {{
            shapesCtx.beginPath();
            shapesCtx.moveTo(shapeStartX, shapeStartY);
            shapesCtx.lineTo(p.x, p.y);
            shapesCtx.stroke();
          }});
        }} else if (currentTool === "circle") {{
          redrawShapesCanvas();
          const r = Math.hypot(p.x - shapeStartX, p.y - shapeStartY);
          strokeShapePreview(() => {{
            shapesCtx.beginPath();
            shapesCtx.arc(shapeStartX, shapeStartY, r, 0, Math.PI * 2);
            shapesCtx.stroke();
          }});
        }}
      }}

      function onPointerUp(evt) {{
        if (currentTool === "move") {{
          draggingShapeId = null;
          return;
        }}

        if (!isDrawing) return;
        isDrawing = false;

        if (currentTool === "line" || currentTool === "circle") {{
          const p = pointerPos(evt);
          const width = Math.max(1, parseInt(brushSize.value || "4", 10));
          if (currentTool === "line") {{
            shapes.push({{ id: nextShapeId++, type: "line", x1: shapeStartX, y1: shapeStartY, x2: p.x, y2: p.y, color: colorPicker.value, width }});
          }} else {{
            const r = Math.hypot(p.x - shapeStartX, p.y - shapeStartY);
            shapes.push({{ id: nextShapeId++, type: "circle", cx: shapeStartX, cy: shapeStartY, r, color: colorPicker.value, width }});
          }}
          redrawShapesCanvas();
        }}
      }}

      function clearDrawing() {{
        saveStrokeSnapshot();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        shapes = [];
        redrawShapesCanvas();
      }}

      function undoStroke() {{
        if (!strokeSnapshots.length) return;
        restoreSnapshot(strokeSnapshots.pop());
      }}

      async function getState() {{
        const r = await fetch(`/state?session=${{encodeURIComponent(sessionId)}}`);
        if (!r.ok) return null;
        return await r.json();
      }}

      async function refreshImage(clearOverlay = false) {{
        await new Promise((resolve) => {{
          const nextSrc = `/image.png?session=${{encodeURIComponent(sessionId)}}&ts=${{Date.now()}}`;
          img.onload = () => {{
            resizeDrawingCanvas(!clearOverlay);
            if (clearOverlay) {{
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              strokeSnapshots = [];
            }}
            resolve();
          }};
          img.onerror = () => resolve();
          img.src = nextSrc;
        }});
      }}

      async function syncUI() {{
        const s = await getState();
        if (!s) return;
        idxEl.textContent = (s.index >= 0 ? s.index : "-");
        totalEl.textContent = (s.total >= 0 ? s.total : "-");

        if (s.total > 0) {{
          slider.max = String(s.total - 1);
          slider.min = "0";
          slider.disabled = false;
          if (follow.checked) {{
            slider.value = String(s.total - 1);
          }} else if (s.index >= 0) {{
            slider.value = String(s.index);
          }}
        }} else {{
          slider.max = "0";
          slider.value = "0";
          slider.disabled = true;
        }}
      }}

      async function go(delta) {{
        const r = await fetch(`/nav?session=${{encodeURIComponent(sessionId)}}&delta=${{delta}}`, {{ method: "POST" }});
        if (r.ok) {{
          follow.checked = false;
          await syncUI();
          await refreshImage(true);
          setStatus(delta < 0 ? "back" : "forward");
        }}
      }}

      async function setIndex(i) {{
        const r = await fetch(`/goto?session=${{encodeURIComponent(sessionId)}}&index=${{i}}`, {{ method: "POST" }});
        if (r.ok) {{
          follow.checked = false;
          await syncUI();
          await refreshImage(true);
          setStatus("goto");
        }}
      }}

      async function sendCurrentCompositeToChatbot() {{
        sendDrawingBtn.disabled = true;
        setStatus("sending...");
        try {{
          const exportCanvas = document.createElement("canvas");
          const displayRect = img.getBoundingClientRect();
          if (!displayRect.width || !displayRect.height) throw new Error("nothing to send");

          exportCanvas.width = img.naturalWidth || canvas.width;
          exportCanvas.height = img.naturalHeight || canvas.height;
          const exportCtx = exportCanvas.getContext("2d");

          if (img.naturalWidth && img.naturalHeight) {{
            exportCtx.drawImage(img, 0, 0, exportCanvas.width, exportCanvas.height);
          }} else {{
            exportCtx.fillStyle = "white";
            exportCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
          }}

          exportCtx.drawImage(canvas, 0, 0, exportCanvas.width, exportCanvas.height);
          exportCtx.drawImage(shapesCanvas, 0, 0, exportCanvas.width, exportCanvas.height);

          const blob = await new Promise((resolve) => exportCanvas.toBlob(resolve, "image/png"));
          if (!blob) throw new Error("failed to encode png");

          const form = new FormData();
          form.append("file", blob, "drawing.png");

          const resp = await fetch(`/send_image_to_chatbot?session=${{encodeURIComponent(sessionId)}}`, {{
            method: "POST",
            body: form,
          }});

          const data = await resp.json().catch(() => ({{}}));
          if (!resp.ok) throw new Error(data.detail || data.error || "upload failed");
          setStatus("sent to chatbot", 1600);
        }} catch (err) {{
          setStatus(`send failed: ${{err.message || err}}`, 2500);
        }} finally {{
          sendDrawingBtn.disabled = false;
        }}
      }}

      document.getElementById("back").onclick = () => go(-1);
      document.getElementById("fwd").onclick = () => go(1);
      slider.addEventListener("input", (e) => setIndex(parseInt(e.target.value || "0", 10)));
      colorPicker.addEventListener("input", updateActiveToolColor);
      toggleDrawBtn.onclick = () => {{ drawingEnabled = !drawingEnabled; setDrawModeLabel(); }};
      for (const [name, btn] of Object.entries(toolButtons)) {{
        btn.onclick = () => setTool(name);
      }}
      undoStrokeBtn.onclick = undoStroke;
      clearDrawingBtn.onclick = clearDrawing;
      sendDrawingBtn.onclick = sendCurrentCompositeToChatbot;

      document.addEventListener("keydown", (e) => {{
        const tag = (e.target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea") return; // typing (e.g. the text tool), not a shortcut
        if (e.key === "ArrowLeft") go(-1);
        if (e.key === "ArrowRight") go(1);
        if (e.key.toLowerCase() === "f") {{
          follow.checked = !follow.checked;
          setStatus(follow.checked ? "follow latest ON" : "follow latest OFF");
        }}
      }});

      shapesCanvas.addEventListener("pointerdown", onPointerDown);
      shapesCanvas.addEventListener("pointermove", onPointerMove);
      shapesCanvas.addEventListener("pointerup", onPointerUp);
      shapesCanvas.addEventListener("pointerleave", onPointerUp);
      shapesCanvas.addEventListener("pointercancel", onPointerUp);
      window.addEventListener("resize", () => resizeDrawingCanvas());

      async function checkLatestSession() {{
        try {{
          const r = await fetch("/latest_session");
          if (!r.ok) return;
          const data = await r.json();
          if (data.session && data.session !== sessionId) {{
            sessionId = data.session;
            sessEl.textContent = sessionId;
            lastTotal = -1;
            await syncUI();
            await refreshImage(true);
            setStatus("switched to new chat session");
          }}
        }} catch (e) {{
          // ignore transient errors
        }}
      }}

      async function poll() {{
        await checkLatestSession();

        const s = await getState();
        if (!s) return;
        await syncUI();

        if (follow.checked && s.total !== lastTotal) {{
          lastTotal = s.total;
          await refreshImage(true);
          setStatus("new image");
        }} else {{
          lastTotal = s.total;
        }}
      }}

      setTool("pen");
      setInterval(poll, 900);
      poll();
      refreshImage(true);
    </script>
  </body>
</html>
"""


@app.post("/register_session")
def register_session(session: str = Query(...)):
    """
    Called by the chatbot on every chat start so this (possibly long-lived,
    shared) canvas server knows which chat session is currently active.
    """
    global _latest_session
    _latest_session = session
    return {"status": "ok", "session": session}


@app.get("/latest_session")
def latest_session():
    return {"session": _latest_session}


@app.get("/state")
def state(session: str = Query(default=SESSION_ID)):
    imgs, idx = _get_state(session)
    return {"session": session, "total": len(imgs), "index": idx}


@app.post("/nav")
def nav(session: str = Query(default=SESSION_ID), delta: int = Query(...)):
    _move_cursor(session, delta)
    return JSONResponse({"status": "ok"})


@app.post("/goto")
def goto(session: str = Query(default=SESSION_ID), index: int = Query(...)):
    _set_cursor(session, index)
    return JSONResponse({"status": "ok"})


@app.post("/clear_canvas")
def clear_canvas(session: str = Query(default=SESSION_ID)):
    """
    Reset a session's drawing history back to a blank canvas, e.g. when
    starting a brand new practice problem the student needs to draw.
    """
    _set_state(session, [], -1)
    return {"status": "ok", "session": session}


@app.get("/image.png")
def image_png(session: str = Query(default=SESSION_ID)):
    imgs, idx = _get_state(session)
    if not imgs or idx < 0 or idx >= len(imgs):
      # Create blank white canvas
      img = Image.new("RGB", (800, 600), (255, 255, 255))
      buf = BytesIO()
      img.save(buf, format="PNG")
      return Response(content=buf.getvalue(), media_type="image/png")
    return Response(content=imgs[idx], media_type="image/png")


@app.post("/send_image_to_canvas")
async def send_image_to_canvas(
    file: UploadFile = File(...),
    session: str = Query(default=SESSION_ID),
):
    """
    Accepts multipart/form-data with a single file field named "file".
    Optional query param: ?session=<id>
    If omitted, uses SESSION_ID passed via argv.
    """
    png = await file.read()
    if not png:
        raise HTTPException(status_code=400, detail="empty upload")

    new_idx = _push_image(session, png)
    imgs, _ = _get_state(session)
    return {"status": "ok", "session": session, "index": new_idx, "total": len(imgs)}


@app.post("/send_image_to_chatbot")
async def send_image_to_chatbot(
    file: UploadFile = File(...),
    session: str = Query(default=SESSION_ID),
):
    """
    Proxy a user-annotated image back to the chatbot server.

    The payload is forwarded as multipart/form-data with the same `file` field,
    and the session is included as `session_id` to match the old tkinter flow.
    """
    png = await file.read()
    if not png:
        raise HTTPException(status_code=400, detail="empty upload")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file.filename or "drawing.png", BytesIO(png), "image/png")}
            response = await client.post(
                CHATBOT_UPLOAD_URL,
                params={"session_id": session},
                files=files,
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"failed to reach chatbot upload endpoint: {e}") from e

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"chatbot upload rejected image ({response.status_code}): {response.text}",
        )

    return {
        "status": "ok",
        "session": session,
        "chatbot_upload_url": CHATBOT_UPLOAD_URL,
        "chatbot_response": response.text,
    }


def main():
    # Bind localhost (client should POST to 127.0.0.1)
    # uvicorn.run(app, host="127.0.0.1", port=8081, log_level="warning")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="warning")


if __name__ == "__main__":
    main()
