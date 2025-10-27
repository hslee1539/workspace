"""FastAPI 기반 VS Code Web 세션 포털."""
from __future__ import annotations

import asyncio
import os
import secrets
import socket
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
SESSION_ROOT = BASE_DIR / "session"
DEVCONTAINER_TEMPLATE = BASE_DIR / "templates" / "devcontainer.json.tpl"
DEFAULT_IMAGE = os.environ.get("DEV_CONTAINER_IMAGE", "android-dev-base:latest")
DEFAULT_ACCESS_HOST = os.environ.get("PORTAL_ACCESS_HOST", "127.0.0.1")

SESSION_ROOT.mkdir(exist_ok=True)


def slugify(value: str) -> str:
    """간단한 슬러그 생성기."""
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789"
    value = value.strip().lower()
    slug_chars = []
    prev_dash = False
    for ch in value:
        if ch in allowed:
            slug_chars.append(ch)
            prev_dash = False
        elif ch.isalnum():
            slug_chars.append(ch.lower())
            prev_dash = False
        else:
            if not prev_dash:
                slug_chars.append("-")
                prev_dash = True
    slug = "".join(slug_chars).strip("-")
    return slug


class SessionStatus(str, Enum):
    """세션 실행 상태."""

    PENDING = "pending"
    LAUNCHING = "launching"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class SessionInfo:
    """컨테이너 세션 정보."""

    id: str
    project_name: str
    git_url: Optional[str]
    workspace_dir: Path
    port: int
    password: str
    container_name: str
    status: SessionStatus = SessionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    access_url: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.id,
            "project_name": self.project_name,
            "git_url": self.git_url,
            "port": self.port,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "access_url": self.access_url,
        }


class PortAllocator:
    """코드 서버 바인딩에 사용할 포트 관리."""

    def __init__(self, start: int = 20000, end: int = 21000) -> None:
        if end <= start:
            raise ValueError("end 포트는 start 보다 커야 합니다.")
        self._start = start
        self._end = end
        self._lock = threading.Lock()
        self._next = start
        self._allocated: Dict[int, str] = {}

    def acquire(self, session_id: str) -> int:
        with self._lock:
            for _ in range(self._start, self._end):
                candidate = self._next
                self._next += 1
                if self._next >= self._end:
                    self._next = self._start
                if candidate in self._allocated:
                    continue
                if self._is_port_in_use(candidate):
                    continue
                self._allocated[candidate] = session_id
                return candidate
        raise RuntimeError("사용 가능한 포트가 없습니다.")

    def release(self, port: int) -> None:
        with self._lock:
            self._allocated.pop(port, None)

    @staticmethod
    def _is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)
            result = sock.connect_ex(("127.0.0.1", port))
        return result == 0


class SessionManager:
    """세션 생명주기 관리."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._lock = threading.Lock()
        self._ports = PortAllocator()

    def create_session(self, git_url: str, project_name: str) -> SessionInfo:
        session_id = uuid.uuid4().hex[:8]
        slug = slugify(project_name) if project_name else ""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        folder_name = f"{timestamp}-{slug or session_id}"
        workspace_dir = SESSION_ROOT / folder_name
        port = self._ports.acquire(session_id)
        password = secrets.token_urlsafe(16)
        container_slug = slugify(f"vscode-{project_name}-{session_id}") or f"session-{session_id}"
        container_name = f"portal-{container_slug}"
        session = SessionInfo(
            id=session_id,
            project_name=project_name or folder_name,
            git_url=git_url or None,
            workspace_dir=workspace_dir,
            port=port,
            password=password,
            container_name=container_name,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionInfo:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError("세션을 찾을 수 없습니다.") from exc

    def list_sessions(self) -> List[SessionInfo]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def update_session(self, session: SessionInfo, *, status: Optional[SessionStatus] = None,
                       error: Optional[str] = None, access_url: Optional[str] = None) -> None:
        if status is not None:
            session.status = status
        session.updated_at = datetime.utcnow()
        session.error_message = error
        if access_url is not None:
            session.access_url = access_url

    def launch_session(self, session_id: str) -> None:
        try:
            session = self.get_session(session_id)
        except KeyError:
            return
        self.update_session(session, status=SessionStatus.LAUNCHING, error=None)
        try:
            self._prepare_workspace(session)
            self._apply_devcontainer_template(session)
            self._start_container(session)
            access_url = f"http://{DEFAULT_ACCESS_HOST}:{session.port}/?folder=/workspace"
            self.update_session(session, status=SessionStatus.RUNNING, access_url=access_url)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._ports.release(session.port)
            self._stop_container(session.container_name)
            self.update_session(session, status=SessionStatus.ERROR, error=str(exc))

    def stop_session(self, session_id: str) -> None:
        try:
            session = self.get_session(session_id)
        except KeyError:
            return
        self._stop_container(session.container_name)
        self._ports.release(session.port)
        self.update_session(session, status=SessionStatus.STOPPED)

    def _prepare_workspace(self, session: SessionInfo) -> None:
        if session.workspace_dir.exists():
            return
        if session.git_url:
            result = subprocess.run(
                [
                    "git",
                    "clone",
                    session.git_url,
                    str(session.workspace_dir),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git clone 실패: {result.stderr.strip()}")
        else:
            session.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _apply_devcontainer_template(self, session: SessionInfo) -> None:
        if not DEVCONTAINER_TEMPLATE.exists():
            return
        devcontainer_dir = session.workspace_dir / ".devcontainer"
        target_file = devcontainer_dir / "devcontainer.json"
        if target_file.exists():
            return
        devcontainer_dir.mkdir(parents=True, exist_ok=True)
        template_text = DEVCONTAINER_TEMPLATE.read_text(encoding="utf-8")
        name = session.project_name or "Android Dev Container"
        rendered = template_text.replace("__PROJECT_NAME__", name)
        target_file.write_text(rendered, encoding="utf-8")

    def _start_container(self, session: SessionInfo) -> None:
        self._stop_container(session.container_name)
        workspace = session.workspace_dir.resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        if not workspace.exists():
            raise RuntimeError("워크스페이스 경로를 생성하지 못했습니다.")
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            session.container_name,
            "-p",
            f"{session.port}:8080",
            "-v",
            f"{workspace}:/workspace",
            "-e",
            f"PASSWORD={session.password}",
            DEFAULT_IMAGE,
            "code-server",
            "/workspace",
            "--bind-addr",
            "0.0.0.0:8080",
            "--auth",
            "password",
            "--disable-telemetry",
            "--disable-update-check",
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "컨테이너 시작 실패: " + result.stderr.strip()
            )

    @staticmethod
    def _stop_container(container_name: str) -> None:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


manager = SessionManager()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
app = FastAPI(title="Android Dev Container Portal")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    sessions = manager.list_sessions()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "sessions": sessions},
    )


@app.post("/sessions", response_class=HTMLResponse)
async def create_session(
    background_tasks: BackgroundTasks,
    git_url: str = Form(default=""),
    project_name: str = Form(default=""),
) -> RedirectResponse:
    session = manager.create_session(git_url, project_name)
    background_tasks.add_task(manager.launch_session, session.id)
    return RedirectResponse(url=f"/sessions/{session.id}", status_code=303)


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str) -> HTMLResponse:
    try:
        session = manager.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.") from exc
    return templates.TemplateResponse(
        "session_detail.html",
        {"request": request, "session": session},
    )


@app.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str) -> RedirectResponse:
    manager.stop_session(session_id)
    return RedirectResponse(url="/", status_code=303)


@app.get("/sessions/{session_id}/status")
async def session_status(session_id: str) -> Dict[str, Optional[str]]:
    try:
        session = manager.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.") from exc
    return session.as_dict()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    sessions = manager.list_sessions()
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, manager.stop_session, s.id) for s in sessions]
    if tasks:
        await asyncio.gather(*tasks)
