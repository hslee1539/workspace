"""Terminal session helpers."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import pty
import struct
import termios
import fcntl
from typing import Optional

from fastapi import WebSocket

from .sessions import Session


class TerminalSession:
    """Bridge between a websocket and container exec."""

    def __init__(self, session: Session, shell: str = "/bin/bash") -> None:
        self.session = session
        self.shell = shell
        self.process: Optional[asyncio.subprocess.Process] = None
        self.master_fd: Optional[int] = None
        self.read_task: Optional[asyncio.Task] = None

    async def start(self, websocket: WebSocket, runtime_binary: str) -> None:
        await websocket.accept()
        loop = asyncio.get_running_loop()
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        def preexec() -> None:
            os.setsid()

        self.process = await asyncio.create_subprocess_exec(
            runtime_binary,
            "exec",
            "-it",
            self.session.container_name,
            self.shell,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=preexec,
        )
        os.close(slave_fd)

        async def reader() -> None:
            assert self.master_fd is not None
            while True:
                data = await loop.run_in_executor(None, os.read, self.master_fd, 1024)
                if not data:
                    break
                await websocket.send_text(data.decode("utf-8", errors="ignore"))
            await websocket.close()

        self.read_task = asyncio.create_task(reader())

        try:
            while True:
                message = await websocket.receive_text()
                payload = json.loads(message)
                msg_type = payload.get("type")
                if msg_type == "input":
                    data = payload.get("data", "")
                    if self.master_fd is not None:
                        os.write(self.master_fd, data.encode("utf-8"))
                elif msg_type == "resize":
                    cols = int(payload.get("cols", 80))
                    rows = int(payload.get("rows", 24))
                    self._resize(cols, rows)
        except Exception:
            pass
        finally:
            await self.close()

    async def close(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()
        if self.master_fd is not None:
            os.close(self.master_fd)
            self.master_fd = None
        if self.read_task:
            self.read_task.cancel()
            with contextlib.suppress(Exception):
                await self.read_task
            self.read_task = None

    def _resize(self, cols: int, rows: int) -> None:
        if self.master_fd is None:
            return
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
