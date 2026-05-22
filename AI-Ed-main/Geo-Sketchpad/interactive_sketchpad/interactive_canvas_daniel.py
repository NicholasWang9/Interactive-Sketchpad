#!/usr/bin/env python3
import sys
import threading
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, JSONResponse
import uvicorn

# Usage:
#   python interactive_canvas.py <SESSION_ID>
SESSION_ID = sys.argv[1] if len(sys.argv) > 1 else "default"

app = FastAPI()

# In-memory history per session_id:
#   history[session_id] = ([png_bytes0, png_bytes1, ...], cursor_index)
_history: Dict[str, Tuple[List[bytes], int]] = {}
_lock = threading.Lock()

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
        # drop oldest, adjust index
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
    # Web UI: back/forward + slider + auto-follow option
    return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>Interactive Sketchpad Canvas (Web)</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; }}
      .meta {{ color: #666; margin: 8px 0; }}
      .bar {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 12px 0; }}
      button {{ padding: 6px 10px; }}
      input[type="range"] {{ width: 320px; }}
      img {{ max-width: 95vw; max-height: 85vh; border: 1px solid #ddd; }}
      code {{ background: #f6f6f6; padding: 2px 4px; border-radius: 4px; }}
    </style>
  </head>
  <body>
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

    <div>
      <img id="img" src="/image.png?session={session}&ts=0" alt="No image yet"/>
    </div>

    <div class="meta">
      Shortcuts: <code>←</code>/<code>→</code> for back/forward, <code>f</code> toggles follow-latest.
    </div>

    <script>
      const sessionId = "{session}";
      const img = document.getElementById("img");
      const idxEl = document.getElementById("idx");
      const totalEl = document.getElementById("total");
      const statusEl = document.getElementById("status");
      const slider = document.getElementById("slider");
      const follow = document.getElementById("follow");

      async function getState() {{
        const r = await fetch(`/state?session=${{encodeURIComponent(sessionId)}}`);
        if (!r.ok) return null;
        return await r.json();
      }}

      function setStatus(t) {{
        statusEl.textContent = t || "";
        if (t) setTimeout(() => {{ statusEl.textContent = ""; }}, 900);
      }}

      async function refreshImage() {{
        img.src = `/image.png?session=${{encodeURIComponent(sessionId)}}&ts=${{Date.now()}}`;
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

          // If following latest, keep slider at latest index
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
          await refreshImage();
          setStatus(delta < 0 ? "back" : "forward");
        }}
      }}

      async function setIndex(i) {{
        const r = await fetch(`/goto?session=${{encodeURIComponent(sessionId)}}&index=${{i}}`, {{ method: "POST" }});
        if (r.ok) {{
          follow.checked = false;
          await syncUI();
          await refreshImage();
          setStatus("goto");
        }}
      }}

      document.getElementById("back").onclick = () => go(-1);
      document.getElementById("fwd").onclick = () => go(1);

      slider.addEventListener("input", (e) => {{
        const i = parseInt(e.target.value || "0", 10);
        setIndex(i);
      }});

      document.addEventListener("keydown", (e) => {{
        if (e.key === "ArrowLeft") go(-1);
        if (e.key === "ArrowRight") go(1);
        if (e.key.toLowerCase() === "f") {{
          follow.checked = !follow.checked;
          setStatus(follow.checked ? "follow latest ON" : "follow latest OFF");
        }}
      }});

      // Poll state; if follow-latest is on and a new image arrives, jump to latest.
      let lastTotal = -1;
      async function poll() {{
        const s = await getState();
        if (!s) return;
        await syncUI();

        if (follow.checked && s.total !== lastTotal) {{
          // new image arrived
          lastTotal = s.total;
          await refreshImage();
          setStatus("new image");
        }} else {{
          lastTotal = s.total;
        }}
      }}

      setInterval(poll, 900);
      poll();
      refreshImage();
    </script>
  </body>
</html>
"""


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


@app.get("/image.png")
def image_png(session: str = Query(default=SESSION_ID)):
    imgs, idx = _get_state(session)
    if not imgs or idx < 0 or idx >= len(imgs):
        return Response(status_code=204)
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


def main():
    # Bind localhost (client should POST to 127.0.0.1)
    uvicorn.run(app, host="127.0.0.1", port=8081, log_level="warning")


if __name__ == "__main__":
    main()