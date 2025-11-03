"""Custom lightweight build backend to avoid external setuptools dependency."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from zipfile import ZipFile, ZIP_DEFLATED

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older versions
    import tomli as tomllib  # type: ignore

ROOT = Path(__file__).resolve().parent


@dataclass
class ProjectConfig:
    name: str
    version: str
    description: str
    requires_python: Optional[str]
    dependencies: Sequence[str]
    authors: Sequence[Dict[str, str]]
    packages: Sequence[str]


def _load_pyproject() -> Dict[str, object]:
    cache = getattr(_load_pyproject, "_cache", None)
    if cache is None:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
        setattr(_load_pyproject, "_cache", data)
        cache = data
    return cache  # type: ignore[return-value]


def _normalise_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "_", name.replace("-", "_"))


def _project_config() -> ProjectConfig:
    data = _load_pyproject()
    project = data.get("project", {})
    tool = data.get("tool", {})
    setuptools_cfg = tool.get("setuptools", {}) if isinstance(tool, dict) else {}
    packages = setuptools_cfg.get("packages", []) if isinstance(setuptools_cfg, dict) else []
    if not packages:
        raise RuntimeError("No packages configured in [tool.setuptools].packages")
    name = project.get("name")
    version = project.get("version")
    description = project.get("description", "")
    requires_python = project.get("requires-python")
    dependencies = project.get("dependencies", [])
    authors = project.get("authors", [])
    if not isinstance(name, str) or not isinstance(version, str):
        raise RuntimeError("Project name and version must be defined in pyproject.toml")
    if not isinstance(description, str):
        description = str(description)
    if requires_python is not None and not isinstance(requires_python, str):
        requires_python = str(requires_python)
    if not isinstance(dependencies, list):
        raise RuntimeError("project.dependencies must be a list")
    if not isinstance(authors, list):
        raise RuntimeError("project.authors must be a list")
    return ProjectConfig(
        name=name,
        version=version,
        description=description,
        requires_python=requires_python,
        dependencies=tuple(str(dep) for dep in dependencies),
        authors=tuple(author for author in authors if isinstance(author, dict)),
        packages=tuple(str(pkg) for pkg in packages),
    )


def _metadata_text(cfg: ProjectConfig) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {cfg.name}",
        f"Version: {cfg.version}",
    ]
    if cfg.description:
        lines.append(f"Summary: {cfg.description}")
    if cfg.requires_python:
        lines.append(f"Requires-Python: {cfg.requires_python}")
    for author in cfg.authors:
        parts = []
        name = author.get("name")
        email = author.get("email")
        if name:
            parts.append(str(name))
        if email:
            parts.append(f"<{email}>")
        if parts:
            lines.append(f"Author: {' '.join(parts)}")
    for dep in cfg.dependencies:
        lines.append(f"Requires-Dist: {dep}")
    lines.append("")
    return "\n".join(lines)


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: workspace-build-backend 0.1",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _install_entries(cfg: ProjectConfig) -> List[Tuple[str, bytes]]:
    entries: List[Tuple[str, bytes]] = []
    for package in cfg.packages:
        package_path = ROOT / package
        if not package_path.exists():
            raise FileNotFoundError(f"Configured package '{package}' does not exist at {package_path}")
        for path in package_path.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(ROOT).as_posix()
                entries.append((rel_path, path.read_bytes()))
    return entries


def _dist_info_entries(cfg: ProjectConfig, editable: bool) -> List[Tuple[str, bytes]]:
    dist_name = _normalise_name(cfg.name)
    dist_info_dir = f"{dist_name}-{cfg.version}.dist-info"
    entries = [
        (f"{dist_info_dir}/METADATA", _metadata_text(cfg).encode("utf-8")),
        (f"{dist_info_dir}/WHEEL", _wheel_text().encode("utf-8")),
        (f"{dist_info_dir}/INSTALLER", b"pip\n"),
    ]
    if editable:
        url = Path(ROOT).resolve().as_uri()
        direct_url = {"url": url, "dir_info": {"editable": True}}
        entries.append((f"{dist_info_dir}/direct_url.json", json.dumps(direct_url, indent=2).encode("utf-8")))
    return entries


def _write_wheel(filename: Path, entries: List[Tuple[str, bytes]]) -> None:
    dist_info_dir = next((name.split("/")[0] for name, _ in entries if name.endswith("/METADATA")), None)
    if dist_info_dir is None:
        raise RuntimeError("METADATA file is required in wheel")
    record_path = f"{dist_info_dir}/RECORD"
    records: List[str] = []
    for name, data in entries:
        digest = hashlib.sha256(data).digest()
        b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        records.append(f"{name},sha256={b64},{len(data)}")
    records.append(f"{record_path},,")
    record_bytes = ("\n".join(records) + "\n").encode("utf-8")
    with ZipFile(filename, "w", compression=ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
        zf.writestr(record_path, record_bytes)


def build_wheel(wheel_directory: str, config_settings: Optional[Dict[str, object]] = None, metadata_directory: Optional[str] = None) -> str:
    cfg = _project_config()
    dist_name = _normalise_name(cfg.name)
    filename = f"{dist_name}-{cfg.version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / filename
    entries = _install_entries(cfg) + _dist_info_entries(cfg, editable=False)
    _write_wheel(wheel_path, entries)
    return filename


def build_editable(wheel_directory: str, config_settings: Optional[Dict[str, object]] = None, metadata_directory: Optional[str] = None) -> str:
    cfg = _project_config()
    dist_name = _normalise_name(cfg.name)
    filename = f"{dist_name}-{cfg.version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / filename
    project_path = ROOT.as_posix()
    pth_content = (project_path + os.linesep).encode("utf-8")
    entries = [(f"{dist_name}.pth", pth_content)] + _dist_info_entries(cfg, editable=True)
    _write_wheel(wheel_path, entries)
    return filename


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings: Optional[Dict[str, object]] = None) -> str:
    cfg = _project_config()
    dist_name = _normalise_name(cfg.name)
    dist_info = Path(metadata_directory) / f"{dist_name}-{cfg.version}.dist-info"
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata_text(cfg), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "INSTALLER").write_text("pip\n", encoding="utf-8")
    return dist_info.name


def build_sdist(sdist_directory: str, config_settings: Optional[Dict[str, object]] = None) -> str:
    cfg = _project_config()
    dist_name = _normalise_name(cfg.name)
    filename = f"{dist_name}-{cfg.version}.tar.gz"
    sdist_path = Path(sdist_directory) / filename
    with tarfile.open(sdist_path, "w:gz") as tar:
        for package in cfg.packages:
            tar.add(ROOT / package, arcname=f"{cfg.name}-{cfg.version}/{package}")
        for extra in ("pyproject.toml", "README.md", "Dockerfile"):
            extra_path = ROOT / extra
            if extra_path.exists():
                tar.add(extra_path, arcname=f"{cfg.name}-{cfg.version}/{extra}")
        for optional_dir in ("scripts", "templates"):
            dir_path = ROOT / optional_dir
            if dir_path.exists():
                tar.add(dir_path, arcname=f"{cfg.name}-{cfg.version}/{optional_dir}")
    return filename


def get_requires_for_build_wheel(config_settings: Optional[Dict[str, object]] = None) -> List[str]:
    return []


def get_requires_for_build_editable(config_settings: Optional[Dict[str, object]] = None) -> List[str]:
    return []


def get_requires_for_build_sdist(config_settings: Optional[Dict[str, object]] = None) -> List[str]:
    return []


def _supported_features() -> List[str]:
    return ["build_editable"]
