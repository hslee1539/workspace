from __future__ import annotations

import logging
import os
import pty
import select
import shlex
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


LOGGER = logging.getLogger("server.terminal")


@dataclass(frozen=True)
class ContainerBackend:
    runtime: str
    label: str
    image: str
    extra_args: Tuple[str, ...] = ()

    def build_command(self, session_id: str, session_dir: Path) -> tuple[list[str], str]:
        workdir = os.environ.get("WORKSPACE_CONTAINER_WORKDIR", "/workspace")
        host_dir = str(session_dir)
        volume = f"{host_dir}:{workdir}"
        container_name = _sanitize_container_name(session_id)
        command: list[str] = [
            self.runtime,
            "run",
            "--rm",
            "-i",
            "-t",
            "--name",
            container_name,
            "-v",
            volume,
            "-w",
            workdir,
        ]
        if self.extra_args:
            command.extend(self.extra_args)
        command.append(self.image)
        shell = os.environ.get("WORKSPACE_CONTAINER_SHELL", "/bin/bash")
        command.append(shell)
        return command, container_name

    def describe(self) -> str:
        return f"{self.label} 컨테이너 · 이미지 {self.image}"


def _sanitize_container_name(session_id: str) -> str:
    base = session_id.lower()
    sanitized = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in base)
    sanitized = sanitized.strip("-_.") or "session"
    return f"devsession-{sanitized}"


def detect_container_backend() -> Optional[ContainerBackend]:
    if os.environ.get("WORKSPACE_FORCE_HOST_TERMINAL"):
        LOGGER.info("환경 변수로 인해 컨테이너 터미널이 비활성화되었습니다.")
        return None

    runtime_overrides = os.environ.get("WORKSPACE_CONTAINER_RUNTIME")
    if runtime_overrides:
        candidates = [item.strip() for item in runtime_overrides.split(",") if item.strip()]
    else:
        candidates = ["docker", "podman"]

    default_image = os.environ.get(
        "WORKSPACE_CONTAINER_IMAGE",
        "mcr.microsoft.com/devcontainers/base:ubuntu",
    )
    args_env = os.environ.get("WORKSPACE_CONTAINER_ARGS", "")
    extra_args: Tuple[str, ...] = tuple(shlex.split(args_env)) if args_env else ()
    label_map = {"docker": "Docker", "podman": "Podman"}

    for runtime in candidates:
        if shutil.which(runtime):
            label = label_map.get(runtime.lower(), runtime.capitalize())
            LOGGER.info(
                "컨테이너 런타임을 사용합니다: runtime=%s, image=%s, extra_args=%s",
                runtime,
                default_image,
                extra_args,
            )
            return ContainerBackend(runtime=runtime, label=label, image=default_image, extra_args=extra_args)

    LOGGER.info(
        "사용 가능한 컨테이너 런타임을 찾지 못했습니다. 호스트 셸을 사용합니다: candidates=%s",
        candidates,
    )
    return None


class TerminalSession:
    def __init__(
        self,
        session_id: str,
        session_dir: Path,
        backend: Optional[ContainerBackend],
    ) -> None:
        self._session_id = session_id
        self._session_dir = Path(session_dir)
        self._master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        self._backend = backend
        self._container_name: Optional[str] = None
        if backend:
            command, container_name = backend.build_command(session_id, self._session_dir)
            self._container_name = container_name
            LOGGER.info(
                "터미널 컨테이너 실행 준비: session_id=%s, runtime=%s, image=%s, name=%s",
                session_id,
                backend.runtime,
                backend.image,
                container_name,
            )
            try:
                self._process = subprocess.Popen(
                    command,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    env=env,
                    close_fds=True,
                )
            except OSError as exc:
                os.close(slave_fd)
                os.close(self._master_fd)
                raise RuntimeError(f"컨테이너를 시작하지 못했습니다: {exc}") from exc
            self._backend_description = backend.describe()
        else:
            shell = os.environ.get("SHELL", "/bin/bash")
            LOGGER.info(
                "호스트 터미널 세션을 시작합니다: session_id=%s, shell=%s",
                session_id,
                shell,
            )
            try:
                self._process = subprocess.Popen(
                    [shell],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    cwd=str(self._session_dir),
                    env=env,
                    close_fds=True,
                )
            except OSError as exc:
                os.close(slave_fd)
                os.close(self._master_fd)
                raise RuntimeError(f"셸을 시작하지 못했습니다: {exc}") from exc
            self._backend_description = f"호스트 셸 · {shell}"
        os.close(slave_fd)
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._closed = False
        self._reader = threading.Thread(target=self._drain_output, daemon=True)
        self._reader.start()
        LOGGER.info(
            "새 터미널 세션을 시작했습니다: session_id=%s, cwd=%s, pid=%s, backend=%s",
            session_id,
            self._session_dir,
            self._process.pid,
            self._backend_description,
        )

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def read(self, offset: int) -> tuple[int, bytes, bool]:
        with self._lock:
            if offset < 0:
                offset = 0
            if offset > len(self._buffer):
                offset = len(self._buffer)
            data = bytes(self._buffer[offset:])
            new_offset = len(self._buffer)
            closed = self._closed
        return new_offset, data, closed

    def write(self, data: bytes) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("터미널 세션이 종료되었습니다.")
        try:
            os.write(self._master_fd, data)
        except OSError as exc:
            raise RuntimeError(f"터미널 입력에 실패했습니다: {exc}") from exc

    def _drain_output(self) -> None:
        try:
            while True:
                if self._process.poll() is not None:
                    ready, _, _ = select.select([self._master_fd], [], [], 0)
                    if not ready:
                        break
                ready, _, _ = select.select([self._master_fd], [], [], 0.2)
                if self._master_fd in ready:
                    try:
                        chunk = os.read(self._master_fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    with self._lock:
                        self._buffer.extend(chunk)
                if self._process.poll() is not None and not ready:
                    break
        finally:
            with self._lock:
                self._closed = True
            try:
                os.close(self._master_fd)
            except OSError:
                pass
        LOGGER.info("터미널 세션이 종료되었습니다: cwd=%s", self._session_dir)
        if self._backend and self._container_name:
            LOGGER.info(
                "컨테이너 세션이 종료되었습니다: session_id=%s, name=%s",
                self._session_id,
                self._container_name,
            )

    @property
    def backend_description(self) -> str:
        return self._backend_description


class TerminalManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._terminals: dict[str, TerminalSession] = {}
        self._backend = detect_container_backend()

    def ensure(self, session_id: str, session_dir: Path) -> TerminalSession:
        with self._lock:
            terminal = self._terminals.get(session_id)
            if terminal is None or terminal.closed:
                LOGGER.info("터미널 세션 초기화: session_id=%s", session_id)
                try:
                    terminal = TerminalSession(session_id, session_dir, self._backend)
                except RuntimeError as exc:
                    if self._backend is not None:
                        LOGGER.error(
                            "컨테이너 터미널 준비에 실패했습니다. 호스트 셸로 대체합니다: %s",
                            exc,
                        )
                        self._backend = None
                        terminal = TerminalSession(session_id, session_dir, None)
                    else:
                        raise
                self._terminals[session_id] = terminal
            return terminal

    def get(self, session_id: str) -> Optional[TerminalSession]:
        with self._lock:
            return self._terminals.get(session_id)

    def describe_default_backend(self) -> str:
        if self._backend:
            return self._backend.describe()
        shell = os.environ.get("SHELL", "/bin/bash")
        return f"호스트 셸 · {shell}"
