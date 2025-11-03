"""FastAPI application for managing container-based workspace sessions."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .container_runtime import ContainerRuntimeError, detect_runtime
from .file_utils import create_directory, delete_path, list_directory, read_file, write_file
from .sessions import SessionManager
from .terminal import TerminalSession

app = FastAPI(title="Workspace Session Server", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"


class SessionCreate(BaseModel):
    name: str = Field("", description="Human friendly session name")
    image: str = Field(..., description="Container image to use for the session")


class FileWriteRequest(BaseModel):
    path: str
    content: str


class DirectoryCreateRequest(BaseModel):
    path: str


class SessionDependency:
    """Provides access to the shared SessionManager instance."""

    def __init__(self) -> None:
        preferred = os.environ.get("CONTAINER_RUNTIME")
        runtime_candidates = [preferred] if preferred else ["docker", "podman"]
        try:
            runtime = detect_runtime(runtime_candidates)
        except ContainerRuntimeError as exc:
            raise RuntimeError(str(exc)) from exc
        base_dir = Path(os.environ.get("SESSION_BASE_DIR", "sessions"))
        self.manager = SessionManager(base_dir=base_dir, runtime=runtime)
        self.runtime = runtime


session_dependency = SessionDependency()


@app.on_event("startup")
async def ensure_static() -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/images")
async def list_images():
    try:
        images = session_dependency.runtime.list_images()
    except ContainerRuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"images": [image.to_dict() for image in images]}


@app.get("/api/sessions")
async def list_sessions():
    sessions = [session.to_dict() for session in session_dependency.manager.list_sessions()]
    return {"sessions": sessions}


@app.post("/api/sessions", status_code=201)
async def create_session(payload: SessionCreate):
    try:
        session = session_dependency.manager.create_session(name=payload.name, image=payload.image)
    except ContainerRuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return session.to_dict()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        session = session_dependency.manager.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return session.to_dict()


@app.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    try:
        session_dependency.manager.remove_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return None


# File operations ---------------------------------------------------------


def _get_paths(session_id: str, requested_path: Optional[str]):
    try:
        session = session_dependency.manager.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    base_path = session.workspace_path
    rel_path = requested_path or "."
    target = (base_path / rel_path).resolve()
    return base_path, target


@app.get("/api/sessions/{session_id}/files")
async def list_files(session_id: str, path: Optional[str] = None):
    base_path, target = _get_paths(session_id, path)
    try:
        data = list_directory(base_path, target)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Path not found")
    return data


@app.get("/api/sessions/{session_id}/files/content")
async def read_file_content(session_id: str, path: str):
    base_path, target = _get_paths(session_id, path)
    try:
        content = read_file(base_path, target)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except IsADirectoryError:
        raise HTTPException(status_code=400, detail="Cannot read a directory")
    return {"content": content}


@app.put("/api/sessions/{session_id}/files/content")
async def write_file_content(session_id: str, payload: FileWriteRequest):
    base_path, target = _get_paths(session_id, payload.path)
    try:
        write_file(base_path, target, payload.content)
    except IsADirectoryError:
        raise HTTPException(status_code=400, detail="Path is a directory")
    return {"status": "ok"}


@app.post("/api/sessions/{session_id}/files/directories")
async def create_directory_endpoint(session_id: str, payload: DirectoryCreateRequest):
    base_path, target = _get_paths(session_id, payload.path)
    create_directory(base_path, target)
    return {"status": "ok"}


@app.delete("/api/sessions/{session_id}/files")
async def delete_path_endpoint(session_id: str, path: str):
    base_path, target = _get_paths(session_id, path)
    delete_path(base_path, target)
    return {"status": "ok"}


# Terminal ----------------------------------------------------------------


@app.websocket("/api/sessions/{session_id}/terminal")
async def terminal_endpoint(websocket: WebSocket, session_id: str):
    try:
        session = session_dependency.manager.get_session(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return
    terminal = TerminalSession(session)
    try:
        await terminal.start(websocket, runtime_binary=session_dependency.manager.runtime.binary)
    except WebSocketDisconnect:
        pass
    finally:
        await terminal.close()
