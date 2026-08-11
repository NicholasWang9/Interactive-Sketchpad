import logging
import tempfile
import traceback

import chainlit as cl
from chainlit.context import init_ws_context
from chainlit.session import WebsocketSession
from chainlit.utils import mount_chainlit
from fastapi import FastAPI, File, HTTPException, Request, UploadFile

from interactive_sketchpad.chatbot import main

logger = logging.getLogger("interactive_sketchpad")

app = FastAPI()

# Handle uploaded images
@app.post("/upload")
async def upload_image(
    session_id: str,
    text: str = "Here's my work so far: can you help me?",
    file: UploadFile = File(...),
):
    ws_session = WebsocketSession.get_by_id(session_id=session_id)
    if ws_session is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No active chat session found for id {session_id!r}. "
                "This happens if the chat tab was reloaded after the whiteboard "
                "opened (each reload starts a new session) -- reopen the "
                "whiteboard from the current chat tab and try again."
            ),
        )

    try:
        init_ws_context(ws_session)

        content = await file.read()

        image_element = cl.Image(
            name=file.filename, content=content, display="inline", size="large"
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            temp_file_path = temp_file.name  # Get the temporary file path
            image_element.path = temp_file_path

            message = cl.Message(content=text, elements=[image_element])
            await message.send()
            await main(message)
    except Exception as e:
        logger.error("Failed to deliver whiteboard image to chat: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}") from e

    return {"message": "Image received"}


mount_chainlit(app=app, target="chatbot.py", path="/interactive_sketchpad")
