from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
SESSION_ROOT = ROOT_DIR / "session"
TEMPLATE_PATH = ROOT_DIR / "templates" / "devcontainer.json.tpl"


class WorkspaceError(RuntimeError):
    """Raised when preparing the workspace fails."""


@dataclass
class SessionResult:
    session_id: str
    session_dir: Path
    project_name: str
    repo_url: str
    editor_command: Optional[str]
    editor_info: Optional[str] = None


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value


def create_session_dir(project_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = slugify(project_name) if project_name else ""
    dir_name = f"{timestamp}-{slug}" if slug else timestamp
    session_dir = SESSION_ROOT / dir_name
    session_dir.mkdir(parents=True, exist_ok=False)
    return session_dir


def clone_or_initialize(session_dir: Path, repo_url: str) -> None:
    if repo_url:
        try:
            subprocess.run(
                ["git", "clone", repo_url, str(session_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise WorkspaceError(
                f"Git 저장소 클론에 실패했습니다: {exc.stderr.decode(errors='ignore').strip()}"
            ) from exc
    else:
        session_dir.mkdir(parents=True, exist_ok=True)


def apply_devcontainer_template(session_dir: Path, project_name: str) -> None:
    devcontainer_dir = session_dir / ".devcontainer"
    devcontainer_path = devcontainer_dir / "devcontainer.json"
    if devcontainer_path.exists():
        return
    if not TEMPLATE_PATH.exists():
        raise WorkspaceError("devcontainer 템플릿 파일을 찾을 수 없습니다.")
    devcontainer_dir.mkdir(parents=True, exist_ok=True)
    name = project_name or "Android Dev Container"
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = template.replace("__PROJECT_NAME__", name)
    devcontainer_path.write_text(template, encoding="utf-8")


def _try_open_with_editor(session_dir: Path) -> tuple[Optional[str], Optional[str]]:
    candidates = [
        ("code", None),
        ("code-insiders", None),
        ("code-server", "http://127.0.0.1:8080"),
    ]
    for command, info in candidates:
        if shutil.which(command):
            try:
                subprocess.Popen([command, str(session_dir)])
                return command, info
            except OSError:
                continue
    if os.name == "posix" and shutil.which("open"):
        try:
            subprocess.Popen(["open", "-a", "Visual Studio Code", str(session_dir)])
            return "open", None
        except OSError:
            pass
    return None, None


def create_session(repo_url: str, project_name: str) -> SessionResult:
    repo_url = repo_url.strip()
    project_name = project_name.strip()
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)

    session_dir = create_session_dir(project_name)
    if repo_url:
        shutil.rmtree(session_dir)
    clone_or_initialize(session_dir, repo_url)

    apply_devcontainer_template(session_dir, project_name)

    editor_command, editor_info = _try_open_with_editor(session_dir)

    session_id = session_dir.name

    return SessionResult(
        session_id=session_id,
        session_dir=session_dir,
        project_name=project_name or session_dir.name,
        repo_url=repo_url,
        editor_command=editor_command,
        editor_info=editor_info,
    )
