import os
import errno
import shutil
import secrets
import time
import heapq
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

from werkzeug.utils import secure_filename

IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


def _is_image_filename(name: str) -> bool:
    _, ext = os.path.splitext(name)
    return ext.lower() in IMAGE_EXTS


class _MaxStr(str):
    def __lt__(self, other):
        return str(self) > str(other)


@dataclass(frozen=True)
class Counts:
    input: int
    by_label: Dict[str, int]


class ImageStore:
    def __init__(self, input_dir: Path, label_dirs: Dict[str, Path]):
        self._input_dir = input_dir
        self._label_dirs = label_dirs

    @property
    def input_dir(self) -> Path:
        return self._input_dir

    def ensure_dirs(self) -> None:
        if not self._input_dir.exists() or not self._input_dir.is_dir():
            raise FileNotFoundError(f"input_dir does not exist or is not a directory: {str(self._input_dir)!r}")
        for _, d in self._label_dirs.items():
            d.mkdir(parents=True, exist_ok=True)

    def dir_for_folder(self, folder: str) -> Path:
        if folder in ("input", "unlabeled"):
            return self._input_dir
        d = self._label_dirs.get(folder)
        if d is None:
            raise ValueError(f"unknown folder: {folder}")
        return d

    def _list_images_in_dir(self, directory: Path, count: int, processed: Set[str]) -> Tuple[List[str], int]:
        self.ensure_dirs()

        total = 0
        heap: List[_MaxStr] = []
        with os.scandir(directory) as it:
            for entry in it:
                if not entry.is_file():
                    continue
                name = entry.name
                if not name or name.startswith("."):
                    continue
                if name in processed:
                    continue
                if not _is_image_filename(name):
                    continue
                total += 1
                if count <= 0:
                    continue
                if len(heap) < count:
                    heapq.heappush(heap, _MaxStr(name))
                else:
                    if name < heap[0]:
                        heapq.heapreplace(heap, _MaxStr(name))
        batch = sorted(str(x) for x in heap)
        return batch, total

    def list_images(self, count: int, processed: Set[str]) -> Tuple[List[str], int]:
        return self._list_images_in_dir(directory=self._input_dir, count=count, processed=processed)

    def list_images_in_folder(self, folder: str, count: int, processed: Set[str]) -> Tuple[List[str], int]:
        directory = self.dir_for_folder(folder)
        return self._list_images_in_dir(directory=directory, count=count, processed=processed)

    def _move(self, src: Path, dest: Path) -> None:
        try:
            os.replace(src, dest)
        except OSError as e:
            if e.errno == errno.EXDEV:
                shutil.move(str(src), str(dest))
                return
            raise

    def move_between_folders(self, filename: str, source_folder: str, dest_folder: str) -> None:
        self.ensure_dirs()

        src_dir = self.dir_for_folder(source_folder)
        dest_dir = self.dir_for_folder(dest_folder)

        if src_dir == dest_dir:
            return

        src = src_dir / filename
        if not src.exists():
            raise FileNotFoundError(f"file not found: {filename}")
        dest = dest_dir / filename
        self._move(src, dest)

    def move_to_label(self, filename: str, label: str) -> None:
        self.move_between_folders(filename=filename, source_folder="input", dest_folder=label)

    def counts(self) -> Counts:
        self.ensure_dirs()
        input_n = 0
        with os.scandir(self._input_dir) as it:
            for entry in it:
                if entry.is_file() and _is_image_filename(entry.name):
                    input_n += 1

        by_label: Dict[str, int] = {}
        for label, d in self._label_dirs.items():
            n = 0
            if d.exists() and d.is_dir():
                with os.scandir(d) as it:
                    for entry in it:
                        if entry.is_file() and _is_image_filename(entry.name):
                            n += 1
            by_label[label] = n

        return Counts(input=input_n, by_label=by_label)

    def save_upload(self, original_filename: str, data: bytes) -> str:
        self.ensure_dirs()
        safe = secure_filename(original_filename) or "upload"
        base, ext = os.path.splitext(safe)
        if ext.lower() not in IMAGE_EXTS:
            raise ValueError("unsupported file extension")

        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}-{base}{ext.lower()}"
        out = self._input_dir / name
        out.write_bytes(data)
        return name
