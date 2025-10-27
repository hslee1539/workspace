from __future__ import annotations

import os
import pty
import select
import subprocess
import threading
from pathlib import Path
from typing import Optional


class TerminalSession:
    def __init__(self, session_dir: Path) -> None:
        self._session_dir = Path(session_dir)
        self._master_fd, slave_fd = pty.openpty()
        shell = os.environ.get("SHELL", "/bin/bash")
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        self._process = subprocess.Popen(
            [shell],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(self._session_dir),
            env=env,
            close_fds=True,
        )
        os.close(slave_fd)
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._closed = False
        self._reader = threading.Thread(target=self._drain_output, daemon=True)
        self._reader.start()

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


class TerminalManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._terminals: dict[str, TerminalSession] = {}

    def ensure(self, session_id: str, session_dir: Path) -> TerminalSession:
        with self._lock:
            terminal = self._terminals.get(session_id)
            if terminal is None or terminal.closed:
                terminal = TerminalSession(session_dir)
                self._terminals[session_id] = terminal
            return terminal

    def get(self, session_id: str) -> Optional[TerminalSession]:
        with self._lock:
            return self._terminals.get(session_id)
