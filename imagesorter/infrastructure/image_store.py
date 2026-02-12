import errno
import heapq
import os
import secrets
import shutil
import time
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

SOURCE_ALIASES = {"unlabeled", "input"}


def _is_image_filename(name: str) -> bool:
    _, ext = os.path.splitext(name)
    return ext.lower() in IMAGE_EXTS


class _MaxKey:
    def __init__(self, key, name: str):
        self.key = key
        self.name = name

    def __lt__(self, other):
        # Invert ordering so heapq (a min-heap) acts like a max-heap by key.
        return self.key > other.key


@dataclass(frozen=True)
class Counts:
    unlabeled: int
    by_label: Dict[str, int]


class ImageStore:
    def __init__(self, source_dir: Path, label_dirs: Dict[str, Path]):
        self._source_dir = source_dir
        self._label_dirs = label_dirs

    @property
    def source_dir(self) -> Path:
        return self._source_dir

    def ensure_dirs(self) -> None:
        self._source_dir.mkdir(parents=True, exist_ok=True)
        for _, d in self._label_dirs.items():
            d.mkdir(parents=True, exist_ok=True)

    def dir_for_folder(self, folder: str) -> Path:
        if folder in SOURCE_ALIASES:
            return self._source_dir
        d = self._label_dirs.get(folder)
        if d is None:
            raise ValueError(f"unknown folder: {folder}")
        return d

    def _list_images_in_dir(self, directory: Path, count: int, processed: Set[str]) -> Tuple[List[str], int]:
        self.ensure_dirs()

        total = 0
        heap: List[_MaxKey] = []
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
                try:
                    mtime_ns = entry.stat(follow_symlinks=False).st_mtime_ns
                except OSError:
                    mtime_ns = 0
                key = (mtime_ns, name)
                if count <= 0:
                    continue
                if len(heap) < count:
                    heapq.heappush(heap, _MaxKey(key, name))
                else:
                    # heap[0] is the current worst (largest) by key
                    if key < heap[0].key:
                        heapq.heapreplace(heap, _MaxKey(key, name))

        heap.sort(key=lambda x: x.key)
        batch = [x.name for x in heap]
        return batch, total

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

    def counts(self) -> Counts:
        self.ensure_dirs()
        source_n = 0
        with os.scandir(self._source_dir) as it:
            for entry in it:
                if entry.is_file() and _is_image_filename(entry.name):
                    source_n += 1

        by_label: Dict[str, int] = {}
        for label, d in self._label_dirs.items():
            n = 0
            if d.exists() and d.is_dir():
                with os.scandir(d) as it:
                    for entry in it:
                        if entry.is_file() and _is_image_filename(entry.name):
                            n += 1
            by_label[label] = n

        return Counts(unlabeled=source_n, by_label=by_label)

    def save_upload(self, original_filename: str, data: bytes) -> str:
        self.ensure_dirs()
        safe = secure_filename(original_filename) or "upload"
        base, ext = os.path.splitext(safe)
        if ext.lower() not in IMAGE_EXTS:
            raise ValueError("unsupported file extension")

        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}-{base}{ext.lower()}"
        out = self._source_dir / name
        out.write_bytes(data)
        return name
