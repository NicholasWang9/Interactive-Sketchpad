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
# Matches the older tkinter version's behavior by default.
CHATBOT_UPLOAD_URL = os.environ.get("CHATBOT_UPLOAD_URL", "http://127.0.0.1:8000/upload")

# Chat UI to embed alongside the canvas (the Chainlit app).
CHAT_UI_URL = os.environ.get("CHAT_UI_URL", "http://127.0.0.1:8000/interactive_sketchpad")

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
      }}
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
      #baseImg {{
        display: block;
        max-width: 95vw;
        max-height: 85vh;
        user-select: none;
        -webkit-user-drag: none;
      }}
      #drawCanvas {{
        position: absolute;
        inset: 0;
        touch-action: none;
        cursor: crosshair;
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
        <h2>Interactive Sketchpad Canvas (Web)</h2>
        <div class="meta">Session: <code id="sess">{session}</code></div>

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
          <label class="meta">Color <input id="colorPicker" type="color" value="#d62828" /></label>
          <label class="meta">Brush <input id="brushSize" type="number" min="1" max="64" step="1" value="4" /></label>
          <button id="eraser">Eraser</button>
          <button id="undoStroke">Undo stroke</button>
          <button id="clearDrawing">Clear drawing</button>
          <span class="sep">|</span>
          <button id="sendDrawing">Send image back to tutor</button>
        </div>

        <div class="canvas-wrap" id="canvasWrap">
          <img id="baseImg" src="/image.png?session={session}&ts=0" alt="No image yet" draggable="false" />
          <canvas id="drawCanvas"></canvas>
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
      const wrap = document.getElementById("canvasWrap");
      const ctx = canvas.getContext("2d");
      const idxEl = document.getElementById("idx");
      const totalEl = document.getElementById("total");
      const statusEl = document.getElementById("status");
      const slider = document.getElementById("slider");
      const follow = document.getElementById("follow");
      const colorPicker = document.getElementById("colorPicker");
      const brushSize = document.getElementById("brushSize");
      const toggleDrawBtn = document.getElementById("toggleDraw");
      const eraserBtn = document.getElementById("eraser");
      const undoStrokeBtn = document.getElementById("undoStroke");
      const clearDrawingBtn = document.getElementById("clearDrawing");
      const sendDrawingBtn = document.getElementById("sendDrawing");

      let drawingEnabled = true;
      let eraserMode = false;
      let isDrawing = false;
      let lastX = 0;
      let lastY = 0;
      let lastTotal = -1;
      let strokeSnapshots = [];

      function setStatus(t, ms = 1200) {{
        statusEl.textContent = t || "";
        if (t) setTimeout(() => {{ if (statusEl.textContent === t) statusEl.textContent = ""; }}, ms);
      }}

      function resizeDrawingCanvas() {{
        const rect = img.getBoundingClientRect();
        if (!rect.width || !rect.height) return;

        const snapshot = canvas.toDataURL("image/png");
        canvas.width = Math.round(rect.width);
        canvas.height = Math.round(rect.height);
        canvas.style.width = `${{Math.round(rect.width)}}px`;
        canvas.style.height = `${{Math.round(rect.height)}}px`;

        const restore = new Image();
        restore.onload = () => {{
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(restore, 0, 0, canvas.width, canvas.height);
        }};
        restore.src = snapshot;
      }}

      function pointerPos(evt) {{
        const rect = canvas.getBoundingClientRect();
        return {{
          x: evt.clientX - rect.left,
          y: evt.clientY - rect.top,
        }};
      }}

      function saveStrokeSnapshot() {{
        strokeSnapshots.push(canvas.toDataURL("image/png"));
        if (strokeSnapshots.length > 200) strokeSnapshots.shift();
      }}

      function restoreSnapshot(dataUrl) {{
        const im = new Image();
        im.onload = () => {{
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(im, 0, 0, canvas.width, canvas.height);
        }};
        im.src = dataUrl;
      }}

      function setDrawModeLabel() {{
        toggleDrawBtn.textContent = drawingEnabled ? "Disable drawing" : "Enable drawing";
        eraserBtn.textContent = eraserMode ? "Use pen" : "Eraser";
        canvas.style.pointerEvents = drawingEnabled ? "auto" : "none";
        canvas.style.cursor = drawingEnabled ? (eraserMode ? "cell" : "crosshair") : "default";
      }}

      function beginStroke(evt) {{
        if (!drawingEnabled) return;
        evt.preventDefault();
        saveStrokeSnapshot();
        isDrawing = true;
        const p = pointerPos(evt);
        lastX = p.x;
        lastY = p.y;
      }}

      function drawStroke(evt) {{
        if (!isDrawing || !drawingEnabled) return;
        evt.preventDefault();
        const p = pointerPos(evt);

        ctx.save();
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.lineWidth = Math.max(1, parseInt(brushSize.value || "4", 10));

        if (eraserMode) {{
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

      function endStroke() {{
        isDrawing = false;
      }}

      function clearDrawing() {{
        saveStrokeSnapshot();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
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
            resizeDrawingCanvas();
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
      toggleDrawBtn.onclick = () => {{ drawingEnabled = !drawingEnabled; setDrawModeLabel(); }};
      eraserBtn.onclick = () => {{ eraserMode = !eraserMode; setDrawModeLabel(); }};
      undoStrokeBtn.onclick = undoStroke;
      clearDrawingBtn.onclick = clearDrawing;
      sendDrawingBtn.onclick = sendCurrentCompositeToChatbot;

      document.addEventListener("keydown", (e) => {{
        if (e.key === "ArrowLeft") go(-1);
        if (e.key === "ArrowRight") go(1);
        if (e.key.toLowerCase() === "f") {{
          follow.checked = !follow.checked;
          setStatus(follow.checked ? "follow latest ON" : "follow latest OFF");
        }}
      }});

      canvas.addEventListener("pointerdown", beginStroke);
      canvas.addEventListener("pointermove", drawStroke);
      canvas.addEventListener("pointerup", endStroke);
      canvas.addEventListener("pointerleave", endStroke);
      canvas.addEventListener("pointercancel", endStroke);
      img.addEventListener("load", resizeDrawingCanvas);
      window.addEventListener("resize", resizeDrawingCanvas);

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

      setDrawModeLabel();
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
