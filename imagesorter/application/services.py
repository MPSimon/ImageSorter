from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from imagesorter.domain.settings import Settings
from imagesorter.infrastructure.image_store import ImageStore


@dataclass
class AppState:
    processed: Set[str]


class ImageSorterService:
    def __init__(self, store: ImageStore, settings: Settings, state: AppState):
        self._store = store
        self._settings = settings
        self._state = state

    def list_images(self, count: int, folder: str = "input") -> Tuple[List[str], int]:
        processed = self._state.processed if folder in ("input", "unlabeled") else set()
        return self._store.list_images_in_folder(folder=folder, count=count, processed=processed)

    def label_image(self, filename: str, label: str, source_folder: str = "input") -> None:
        self._store.move_between_folders(filename=filename, source_folder=source_folder, dest_folder=label)
        self._state.processed.add(filename)

    def reset_processed(self) -> None:
        self._state.processed.clear()

    def counts(self) -> Dict[str, int]:
        c = self._store.counts()
        out = {"input": c.input}
        out.update(c.by_label)
        return out

    def upload(self, filename: str, data: bytes) -> str:
        return self._store.save_upload(original_filename=filename, data=data)

    def public_config(self) -> Dict:
        return self._settings.to_public_dict()
