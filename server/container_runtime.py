"""Container runtime abstraction for Docker and Podman."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


class ContainerRuntimeError(RuntimeError):
    """Raised when container runtime operations fail."""


@dataclass
class ContainerInfo:
    """Minimal information about a managed container."""

    container_id: str
    name: str
    image: str
    status: str
    created: str
    labels: Dict[str, str]


@dataclass
class ImageInfo:
    """Information about an available container image."""

    repository: str
    tag: str
    image_id: str
    created_since: str
    size: str

    @property
    def reference(self) -> str:
        """Return the preferred reference for the image."""

        repository = self.repository if self.repository != "<none>" else ""
        tag = self.tag if self.tag != "<none>" else ""
        if repository and tag:
            return f"{repository}:{tag}"
        if repository:
            return repository
        if tag:
            return tag
        return self.image_id

    def to_dict(self) -> Dict[str, str]:
        return {
            "repository": self.repository,
            "tag": self.tag,
            "id": self.image_id,
            "created": self.created_since,
            "size": self.size,
            "reference": self.reference,
        }


class ContainerRuntime:
    """Wrapper around Docker/Podman CLI for session management."""

    MANAGED_LABEL = "workspace.session.managed"

    def __init__(self, binary: str = "docker") -> None:
        self.binary = binary
        resolved = shutil.which(binary)
        if not resolved:
            raise ContainerRuntimeError(
                f"Container runtime '{binary}' not found in PATH."
            )
        self.binary = resolved

    def _run(self, *args: str, capture_output: bool = True) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.binary, *args],
                check=True,
                capture_output=capture_output,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ContainerRuntimeError(exc.stderr.strip() or str(exc)) from exc

    def ensure_available(self) -> None:
        self._run("version", capture_output=False)

    # Container lifecycle -------------------------------------------------

    def create_container(
        self,
        *,
        session_id: str,
        name: str,
        image: str,
        workdir: str,
        mount: str,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        env_args: List[str] = []
        for key, value in (env or {}).items():
            env_args.extend(["-e", f"{key}={value}"])
        labels = {
            self.MANAGED_LABEL: "1",
            "workspace.session.id": session_id,
            "workspace.session.name": name,
            "workspace.session.workdir": workdir,
            "workspace.session.mount": mount,
        }
        label_args: List[str] = []
        for key, value in labels.items():
            label_args.extend(["--label", f"{key}={value}"])
        args = [
            "run",
            "-d",
            "--name",
            name,
            "--workdir",
            workdir,
            *label_args,
            "-v",
            mount,
            *env_args,
            image,
            "sleep",
            "infinity",
        ]
        result = self._run(*args)
        return result.stdout.strip()

    def remove_container(self, container_name: str) -> None:
        self._run("rm", "-f", container_name, capture_output=False)

    def list_managed(self) -> List[ContainerInfo]:
        args = [
            "ps",
            "--all",
            "--filter",
            f"label={self.MANAGED_LABEL}=1",
            "--format",
            "{{json .}}",
        ]
        result = self._run(*args)
        containers: List[ContainerInfo] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            info = json.loads(line)
            labels = self._parse_labels(info.get("Labels"))
            containers.append(
                ContainerInfo(
                    container_id=info.get("ID", ""),
                    name=info.get("Names", ""),
                    image=info.get("Image", ""),
                    status=info.get("Status", ""),
                    created=info.get("RunningFor", ""),
                    labels=labels,
                )
            )
        return containers

    def inspect(self, name: str) -> Dict:
        result = self._run("inspect", name)
        data = json.loads(result.stdout)
        if not data:
            raise ContainerRuntimeError(f"Container '{name}' not found")
        return data[0]

    def list_images(self) -> List[ImageInfo]:
        """Return the images available to the runtime."""

        result = self._run("image", "ls", "--format", "{{json .}}")
        images: List[ImageInfo] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            info = json.loads(line)
            images.append(
                ImageInfo(
                    repository=info.get("Repository", ""),
                    tag=info.get("Tag", ""),
                    image_id=info.get("ID", ""),
                    created_since=info.get("CreatedSince", ""),
                    size=info.get("Size", ""),
                )
            )
        return images

    @staticmethod
    def _parse_labels(raw: Optional[str]) -> Dict[str, str]:
        if raw is None:
            return {}
        labels: Dict[str, str] = {}
        for part in raw.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                labels[key] = value
        return labels


def detect_runtime(preferred: Optional[Iterable[str]] = None) -> ContainerRuntime:
    """Return the first available runtime from the preferred list."""

    candidates = list(preferred or ["docker", "podman"])
    errors: List[str] = []
    for binary in candidates:
        try:
            runtime = ContainerRuntime(binary)
            runtime.ensure_available()
            return runtime
        except ContainerRuntimeError as exc:
            errors.append(str(exc))
    message = "; ".join(errors) if errors else "No supported container runtime available"
    raise ContainerRuntimeError(message)
