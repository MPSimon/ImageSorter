import errno
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

SOURCE_FOLDER = "unlabeled"
LEGACY_SOURCE_FOLDER = "input"
LABELS = ("good", "regenerate", "upscale", "bad")
PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MIGRATION_MARKER = ".projects_migration_v1.done"
INITIAL_PROJECT_NAME = "2026-02-12"


@dataclass(frozen=True)
class ProjectPaths:
    name: str
    source_dir: Path
    label_dirs: Dict[str, Path]


class ProjectStore:
    def __init__(self, data_root: Path):
        self._data_root = data_root
        self._projects_root = data_root / "projects"
        self._marker_path = data_root / MIGRATION_MARKER

    @property
    def projects_root(self) -> Path:
        return self._projects_root

    def normalize_project_name(self, raw: str) -> str:
        name = (raw or "").strip().lower()
        if not PROJECT_NAME_RE.fullmatch(name):
            raise ValueError("invalid project name (allowed: lowercase letters, digits, '-' and '_', max 64 chars)")
        return name

    def list_projects(self) -> List[str]:
        if not self._projects_root.exists():
            return []

        projects: List[str] = []
        with os.scandir(self._projects_root) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                if entry.name.startswith("."):
                    continue
                if not PROJECT_NAME_RE.fullmatch(entry.name):
                    continue
                projects.append(entry.name)
        projects.sort()
        return projects

    def project_exists(self, name: str) -> bool:
        project = self.normalize_project_name(name)
        return (self._projects_root / project).is_dir()

    def create_project(self, raw_name: str) -> str:
        name = self.normalize_project_name(raw_name)
        root = self._projects_root / name
        root.mkdir(parents=True, exist_ok=False)
        self.ensure_project_dirs(name)
        return name

    def ensure_project_dirs(self, raw_name: str) -> str:
        name = self.normalize_project_name(raw_name)
        root = self._projects_root / name
        root.mkdir(parents=True, exist_ok=True)
        (root / SOURCE_FOLDER).mkdir(parents=True, exist_ok=True)
        for label in LABELS:
            (root / label).mkdir(parents=True, exist_ok=True)
        return name

    def paths_for_project(self, raw_name: str) -> ProjectPaths:
        name = self.ensure_project_dirs(raw_name)
        root = self._projects_root / name
        return ProjectPaths(
            name=name,
            source_dir=root / SOURCE_FOLDER,
            label_dirs={label: root / label for label in LABELS},
        )

    def ensure_default_project(self) -> str:
        projects = self.list_projects()
        if "default" in projects:
            self.ensure_project_dirs("default")
            return "default"
        if projects:
            self.ensure_project_dirs(projects[0])
            return projects[0]
        self.ensure_project_dirs(INITIAL_PROJECT_NAME)
        return INITIAL_PROJECT_NAME

    def _move(self, src: Path, dst: Path) -> None:
        try:
            os.replace(src, dst)
        except OSError as e:
            if e.errno == errno.EXDEV:
                shutil.move(str(src), str(dst))
                return
            raise

    def _unique_destination(self, destination_dir: Path, name: str) -> Path:
        candidate = destination_dir / name
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        idx = 1
        while True:
            numbered = destination_dir / f"{stem}-{idx}{suffix}"
            if not numbered.exists():
                return numbered
            idx += 1

    def _move_legacy_folder(self, legacy_dir: Path, destination_dir: Path) -> None:
        if not legacy_dir.exists() or not legacy_dir.is_dir():
            return

        destination_dir.mkdir(parents=True, exist_ok=True)
        with os.scandir(legacy_dir) as it:
            for entry in it:
                if not entry.is_file():
                    continue
                src = Path(entry.path)
                dst = self._unique_destination(destination_dir, entry.name)
                self._move(src, dst)

    def _legacy_layout_exists(self) -> bool:
        if (self._data_root / LEGACY_SOURCE_FOLDER).is_dir():
            return True
        return any((self._data_root / label).is_dir() for label in LABELS)

    def migrate_legacy_layout_once(self) -> str:
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._projects_root.mkdir(parents=True, exist_ok=True)

        target_name = INITIAL_PROJECT_NAME
        self.ensure_project_dirs(target_name)

        if self._marker_path.exists():
            return target_name

        if self._legacy_layout_exists():
            target = self.paths_for_project(target_name)
            self._move_legacy_folder(self._data_root / LEGACY_SOURCE_FOLDER, target.source_dir)
            for label, label_dir in target.label_dirs.items():
                self._move_legacy_folder(self._data_root / label, label_dir)

        self._marker_path.write_text("done\n", encoding="utf-8")
        return target_name
