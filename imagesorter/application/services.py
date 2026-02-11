from typing import Dict, List, Tuple

from imagesorter.domain.settings import Settings
from imagesorter.infrastructure.image_store import ImageStore


class ImageSorterService:
    def __init__(self, store: ImageStore, settings: Settings):
        self._store = store
        self._settings = settings

    def list_images(self, count: int, folder: str = "input") -> Tuple[List[str], int]:
        # Don't filter based on per-process memory. With multiple gunicorn workers,
        # that causes inconsistent responses and visible flicker in the UI.
        return self._store.list_images_in_folder(folder=folder, count=count, processed=set())

    def label_image(self, filename: str, label: str, source_folder: str = "input") -> None:
        self._store.move_between_folders(filename=filename, source_folder=source_folder, dest_folder=label)

    def counts(self) -> Dict[str, int]:
        c = self._store.counts()
        out = {"input": c.input}
        out.update(c.by_label)
        return out

    def upload(self, filename: str, data: bytes) -> str:
        return self._store.save_upload(original_filename=filename, data=data)

    def archive_images(self, folder: str) -> int:
        """Archive all images from the specified folder. Returns count of archived images."""
        return self._store.archive_images(folder=folder)

    def public_config(self) -> Dict:
        return self._settings.to_public_dict()
