from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
SESSION_ROOT = ROOT_DIR / "session"
TEMPLATE_PATH = ROOT_DIR / "templates" / "devcontainer.json.tpl"

LOGGER = logging.getLogger("server.workspace")


class WorkspaceError(RuntimeError):
    """Raised when preparing the workspace fails."""


@dataclass
class EditorOption:
    identifier: str
    label: str
    args: List[str]
    info: Optional[str] = None


@dataclass
class SessionResult:
    session_id: str
    session_dir: Path
    project_name: str
    repo_url: str
    editor_command: Optional[str]
    editor_info: Optional[str] = None
    available_editors: List[EditorOption] = field(default_factory=list)


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
    LOGGER.info("세션 디렉터리 생성: %s", session_dir)
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
            LOGGER.info("Git 저장소를 클론했습니다: %s -> %s", repo_url, session_dir)
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise WorkspaceError(
                f"Git 저장소 클론에 실패했습니다: {exc.stderr.decode(errors='ignore').strip()}"
            ) from exc
    else:
        session_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.info("빈 프로젝트 디렉터리를 초기화했습니다: %s", session_dir)


def apply_devcontainer_template(session_dir: Path, project_name: str) -> None:
    devcontainer_dir = session_dir / ".devcontainer"
    devcontainer_path = devcontainer_dir / "devcontainer.json"
    if devcontainer_path.exists():
        LOGGER.debug("기존 devcontainer.json이 존재하여 생성을 건너뜁니다: %s", devcontainer_path)
        return
    if not TEMPLATE_PATH.exists():
        raise WorkspaceError("devcontainer 템플릿 파일을 찾을 수 없습니다.")
    devcontainer_dir.mkdir(parents=True, exist_ok=True)
    name = project_name or "Android Dev Container"
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = template.replace("__PROJECT_NAME__", name)
    devcontainer_path.write_text(template, encoding="utf-8")
    LOGGER.info("devcontainer 템플릿을 생성했습니다: %s", devcontainer_path)


def detect_editor_options() -> List[EditorOption]:
    options: List[EditorOption] = []

    if shutil.which("code"):
        options.append(
            EditorOption(
                identifier="code",
                label="Visual Studio Code (code)",
                args=["code"],
            )
        )

    if shutil.which("code-insiders"):
        options.append(
            EditorOption(
                identifier="code-insiders",
                label="Visual Studio Code Insiders",
                args=["code-insiders"],
            )
        )

    if shutil.which("code-server"):
        options.append(
            EditorOption(
                identifier="code-server",
                label="code-server",
                args=["code-server"],
                info="http://127.0.0.1:8080",
            )
        )

    if os.name == "posix" and shutil.which("open"):
        options.append(
            EditorOption(
                identifier="macos-open-vscode",
                label="Visual Studio Code (macOS)",
                args=["open", "-a", "Visual Studio Code"],
            )
        )

    return options


def launch_editor(option: EditorOption, session_dir: Path) -> None:
    command = option.args + [str(session_dir)]
    try:
        subprocess.Popen(command)
    except OSError as exc:
        raise WorkspaceError(f"에디터 실행에 실패했습니다: {exc}") from exc


def create_session(repo_url: str, project_name: str) -> SessionResult:
    repo_url = repo_url.strip()
    project_name = project_name.strip()
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)

    session_dir = create_session_dir(project_name)
    if repo_url:
        shutil.rmtree(session_dir)
    clone_or_initialize(session_dir, repo_url)

    apply_devcontainer_template(session_dir, project_name)

    available_editors = detect_editor_options()
    editor_command = None
    editor_info = None

    session_id = session_dir.name
    LOGGER.info(
        "세션 구성이 완료되었습니다: session_id=%s, available_editors=%s",
        session_id,
        [option.identifier for option in available_editors] or "(none)",
    )

    return SessionResult(
        session_id=session_id,
        session_dir=session_dir,
        project_name=project_name or session_dir.name,
        repo_url=repo_url,
        editor_command=editor_command,
        editor_info=editor_info,
        available_editors=available_editors,
    )
