"""Session management utilities."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .container_runtime import ContainerRuntime


@dataclass
class Session:
    """Represents a workspace session backed by a container."""

    session_id: str
    name: str
    image: str
    container_name: str
    workspace_path: Path
    created_at: float
    status: str = ""
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.session_id,
            "name": self.name,
            "image": self.image,
            "container": self.container_name,
            "workspacePath": str(self.workspace_path),
            "createdAt": datetime.fromtimestamp(self.created_at).isoformat(),
            "status": self.status,
        }


class SessionManager:
    """Creates and tracks workspace sessions."""

    def __init__(self, base_dir: Path, runtime: ContainerRuntime) -> None:
        self.base_dir = base_dir
        self.runtime = runtime
        self.sessions: Dict[str, Session] = {}
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._load_existing()

    # ------------------------------------------------------------------
    def _load_existing(self) -> None:
        for info in self.runtime.list_managed():
            session_id = info.labels.get("workspace.session.id")
            workspace = info.labels.get("workspace.session.mount", "")
            if not session_id or not workspace:
                continue
            session = Session(
                session_id=session_id,
                name=info.labels.get("workspace.session.name", info.name),
                image=info.image,
                container_name=info.name,
                workspace_path=Path(workspace.split(":", 1)[0]),
                created_at=time.time(),
                status=info.status,
                labels=info.labels,
            )
            self.sessions[session_id] = session

    # ------------------------------------------------------------------
    def _slugify(self, value: str) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-") or "session"

    def _generate_session_id(self) -> str:
        return secrets.token_hex(4)

    def _build_workspace_path(self, name: str, session_id: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = self._slugify(name or "workspace")
        return self.base_dir / f"{timestamp}-{slug}-{session_id}"

    def create_session(
        self,
        *,
        name: str,
        image: str,
    ) -> Session:
        session_id = self._generate_session_id()
        container_name = f"workspace-session-{session_id}"
        workspace_path = self._build_workspace_path(name, session_id)
        workspace_path.mkdir(parents=True, exist_ok=True)
        mount = f"{workspace_path}:/workspace"
        container_id = self.runtime.create_container(
            session_id=session_id,
            name=container_name,
            image=image,
            workdir="/workspace",
            mount=mount,
        )
        session = Session(
            session_id=session_id,
            name=name or container_name,
            image=image,
            container_name=container_name,
            workspace_path=workspace_path,
            created_at=time.time(),
            status=f"Created ({container_id[:12]})",
        )
        self.sessions[session_id] = session
        return session

    def list_sessions(self) -> List[Session]:
        for session in self.sessions.values():
            try:
                info = self.runtime.inspect(session.container_name)
            except Exception:
                continue
            session.status = info.get("State", {}).get("Status", "unknown")
        return sorted(self.sessions.values(), key=lambda s: s.created_at)

    def get_session(self, session_id: str) -> Session:
        if session_id not in self.sessions:
            raise KeyError(session_id)
        return self.sessions[session_id]

    def remove_session(self, session_id: str) -> None:
        session = self.get_session(session_id)
        self.runtime.remove_container(session.container_name)
        self.sessions.pop(session_id, None)


# Utility functions -------------------------------------------------------

def ensure_within(base: Path, target: Path) -> Path:
    """Ensure that *target* is within *base* directory."""

    base = base.resolve()
    target = target.resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Invalid path outside of session workspace")
    return target
