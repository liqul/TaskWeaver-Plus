from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from taskweaver.app.app import TaskWeaverApp
from taskweaver.module.event_emitter import (
    ConfirmationHandler,
    PostEventType,
    RoundEventType,
    SessionEventHandlerBase,
    SessionEventType,
)
from taskweaver.session.session import Session


class WebSocketConfirmationHandler(ConfirmationHandler):
    """Placeholder that signals the event emitter to block for user confirmation.
    
    The actual confirmation is provided via event_emitter.provide_confirmation()
    when the WebSocket client responds.
    """

    def request_confirmation(self, code: str, round_id: str, post_id: Optional[str]) -> bool:
        return True

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@dataclass
class ChatSession:
    session_id: str
    tw_session: Session
    websocket: Optional[WebSocket] = None
    is_processing: bool = False
    pending_files: List[Dict[Literal["name", "path", "content"], Any]] = field(default_factory=list)


class ChatSessionManager:
    def __init__(self):
        self._sessions: Dict[str, ChatSession] = {}
        self._app: Optional[TaskWeaverApp] = None
        self._app_dir: Optional[str] = None
        self._lock = threading.Lock()

    def set_app_dir(self, app_dir: str):
        self._app_dir = app_dir

    def _get_app(self) -> TaskWeaverApp:
        if self._app is None:
            self._app = TaskWeaverApp(app_dir=self._app_dir)
        return self._app

    def create_session(self) -> ChatSession:
        app = self._get_app()
        tw_session = app.get_session()
        chat_session = ChatSession(
            session_id=tw_session.session_id,
            tw_session=tw_session,
        )
        with self._lock:
            self._sessions[chat_session.session_id] = chat_session
        return chat_session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                session.tw_session.stop()
                return True
            return False

    def list_sessions(self) -> List[str]:
        with self._lock:
            return list(self._sessions.keys())

    def cleanup_all(self):
        with self._lock:
            for session in self._sessions.values():
                session.tw_session.stop()
            self._sessions.clear()
        if self._app:
            self._app.stop()
            self._app = None


chat_manager = ChatSessionManager()


class WebSocketEventHandler(SessionEventHandlerBase):
    """Event handler that forwards TaskWeaver events to a WebSocket client."""

    def __init__(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop):
        self.websocket = websocket
        self.loop = loop
        self.last_attachment_id = ""

    def _send(self, msg: Dict[str, Any]):
        asyncio.run_coroutine_threadsafe(
            self.websocket.send_json(msg),
            self.loop,
        )

    def handle_session(
        self,
        type: SessionEventType,
        msg: str,
        extra: Any,
        **kwargs: Any,
    ):
        self._send({
            "type": f"session_{type.name}",
            "message": msg,
        })

    def handle_round(
        self,
        type: RoundEventType,
        msg: str,
        extra: Any,
        round_id: str,
        **kwargs: Any,
    ):
        if type == RoundEventType.round_start:
            self._send({
                "type": "round_start",
                "round_id": round_id,
            })
        elif type == RoundEventType.round_end:
            self._send({
                "type": "round_end",
                "round_id": round_id,
            })
        elif type == RoundEventType.round_error:
            self._send({
                "type": "error",
                "message": msg,
                "round_id": round_id,
            })

    def handle_post(
        self,
        type: PostEventType,
        msg: str,
        extra: Any,
        post_id: str,
        round_id: str,
        **kwargs: Any,
    ):
        if type == PostEventType.post_start:
            self._send({
                "type": "post_start",
                "post_id": post_id,
                "round_id": round_id,
                "role": extra.get("role", "Unknown"),
            })
        elif type == PostEventType.post_end:
            self._send({
                "type": "post_end",
                "post_id": post_id,
                "round_id": round_id,
            })
        elif type == PostEventType.post_message_update:
            self._send({
                "type": "message_update",
                "post_id": post_id,
                "text": msg,
                "is_end": extra.get("is_end", True),
            })
        elif type == PostEventType.post_attachment_update:
            attachment_id = extra.get("id", "")
            attachment_type = extra.get("type")
            is_end = extra.get("is_end", True)
            
            if attachment_id != self.last_attachment_id:
                self._send({
                    "type": "attachment_start",
                    "post_id": post_id,
                    "attachment_id": attachment_id,
                    "attachment_type": attachment_type.name if attachment_type else None,
                })
                self.last_attachment_id = attachment_id
            
            self._send({
                "type": "attachment_update",
                "post_id": post_id,
                "attachment_id": attachment_id,
                "content": msg,
                "is_end": is_end,
            })
            
            if is_end:
                self.last_attachment_id = ""
        elif type == PostEventType.post_status_update:
            self._send({
                "type": "status_update",
                "post_id": post_id,
                "status": msg,
            })
        elif type == PostEventType.post_send_to_update:
            self._send({
                "type": "send_to_update",
                "post_id": post_id,
                "send_to": extra.get("role", "Unknown"),
            })
        elif type == PostEventType.post_execution_output:
            self._send({
                "type": "execution_output",
                "post_id": post_id,
                "stream": extra.get("stream", "stdout"),
                "text": extra.get("text", msg),
            })
        elif type == PostEventType.post_confirmation_request:
            self._send({
                "type": "confirm_request",
                "code": extra.get("code", msg),
                "round_id": round_id,
                "post_id": post_id,
            })


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    session = chat_manager.get_session(session_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return
    
    session.websocket = websocket
    loop = asyncio.get_event_loop()
    handler = WebSocketEventHandler(websocket, loop)
    
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
    })
    
    for chat_round in session.tw_session.memory.conversation.rounds:
        await websocket.send_json({
            "type": "round_start",
            "round_id": chat_round.id,
        })
        
        if chat_round.user_query:
            user_post_id = f"user-{chat_round.id}"
            await websocket.send_json({
                "type": "post_start",
                "post_id": user_post_id,
                "round_id": chat_round.id,
                "role": "User",
            })
            await websocket.send_json({
                "type": "message_update",
                "post_id": user_post_id,
                "text": chat_round.user_query,
                "is_end": True,
            })
            await websocket.send_json({
                "type": "post_end",
                "post_id": user_post_id,
                "round_id": chat_round.id,
            })
        
        for post in chat_round.post_list:
            # Skip User posts - we already sent the user message from user_query
            if post.send_from == "User":
                continue
            
            await websocket.send_json({
                "type": "post_start",
                "post_id": post.id,
                "round_id": chat_round.id,
                "role": post.send_from,
            })
            await websocket.send_json({
                "type": "send_to_update",
                "post_id": post.id,
                "send_to": post.send_to,
            })
            
            for attachment in post.attachment_list:
                await websocket.send_json({
                    "type": "attachment_start",
                    "post_id": post.id,
                    "attachment_id": attachment.id,
                    "attachment_type": attachment.type.name,
                })
                await websocket.send_json({
                    "type": "attachment_update",
                    "post_id": post.id,
                    "attachment_id": attachment.id,
                    "content": attachment.content,
                    "is_end": True,
                })
            
            if post.message:
                await websocket.send_json({
                    "type": "message_update",
                    "post_id": post.id,
                    "text": post.message,
                    "is_end": True,
                })
            
            await websocket.send_json({
                "type": "post_end",
                "post_id": post.id,
                "round_id": chat_round.id,
            })
        
        await websocket.send_json({
            "type": "round_end",
            "round_id": chat_round.id,
        })
    
    await websocket.send_json({"type": "history_complete"})
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "send_message":
                message = data.get("message", "")
                files = data.get("files", [])
                
                if session.is_processing:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Already processing a message",
                    })
                    continue
                
                session.is_processing = True
                
                def run_message():
                    try:
                        session.tw_session.event_emitter.confirmation_handler = WebSocketConfirmationHandler()
                        chat_round = session.tw_session.send_message(
                            message,
                            event_handler=handler,
                            files=files + session.pending_files,
                        )
                        session.pending_files.clear()
                        
                        last_post = chat_round.post_list[-1] if chat_round.post_list else None
                        result_message = last_post.message if last_post and last_post.send_to == "User" else None
                        
                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json({
                                "type": "message_complete",
                                "result": result_message,
                            }),
                            loop,
                        )
                    except Exception as e:
                        logger.exception("Error processing message")
                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json({
                                "type": "error",
                                "message": str(e),
                            }),
                            loop,
                        )
                    finally:
                        session.is_processing = False
                
                threading.Thread(target=run_message, daemon=True).start()
            
            elif msg_type == "confirm":
                approved = data.get("approved", False)
                session.tw_session.event_emitter.provide_confirmation(approved)
            
            elif msg_type == "cancel":
                pass
            
            elif msg_type == "upload_file":
                filename = data.get("filename", "")
                content = data.get("content", "")
                session.pending_files.append({
                    "name": filename,
                    "content": content,
                })
                await websocket.send_json({
                    "type": "file_uploaded",
                    "filename": filename,
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.exception(f"WebSocket error for session {session_id}")
    finally:
        session.websocket = None


@router.post("/sessions")
async def create_chat_session():
    session = chat_manager.create_session()
    return {
        "session_id": session.session_id,
        "status": "created",
    }


@router.get("/sessions")
async def list_chat_sessions():
    sessions = chat_manager.list_sessions()
    return {
        "sessions": [{"session_id": sid} for sid in sessions],
    }


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    if chat_manager.delete_session(session_id):
        return {"status": "deleted"}
    return {"status": "not_found"}


@router.get("/sessions/{session_id}/artifacts/{filename:path}")
async def download_chat_artifact(session_id: str, filename: str):
    """Serve artifacts (images, files) from a chat session's execution directory."""
    session = chat_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    artifact_path = os.path.join(session.tw_session.execution_cwd, filename)

    # Security: ensure the path doesn't escape the execution directory
    real_artifact_path = os.path.realpath(artifact_path)
    real_cwd = os.path.realpath(session.tw_session.execution_cwd)
    if not real_artifact_path.startswith(real_cwd):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(artifact_path):
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(artifact_path)
