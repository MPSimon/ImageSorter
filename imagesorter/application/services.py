from typing import Dict, List, Tuple

from imagesorter.infrastructure.image_store import ImageStore


class ImageSorterService:
    def __init__(self, store: ImageStore, labels: List[str], default_image_count: int = 20, default_grid_columns: int = 5):
        self._store = store
        self._labels = list(labels)
        self._default_image_count = int(default_image_count)
        self._default_grid_columns = int(default_grid_columns)

    def list_images(self, count: int, folder: str = "unlabeled") -> Tuple[List[str], int]:
        # Don't filter based on per-process memory. With multiple gunicorn workers,
        # that causes inconsistent responses and visible flicker in the UI.
        return self._store.list_images_in_folder(folder=folder, count=count, processed=set())

    def label_image(self, filename: str, label: str, source_folder: str = "unlabeled") -> None:
        self._store.move_between_folders(filename=filename, source_folder=source_folder, dest_folder=label)

    def counts(self) -> Dict[str, int]:
        c = self._store.counts()
        out = {"unlabeled": c.unlabeled}
        out.update(c.by_label)
        return out

    def upload(self, filename: str, data: bytes) -> str:
        return self._store.save_upload(original_filename=filename, data=data)

    def public_config(self) -> Dict:
        return {
            "labels": list(self._labels),
            "image_count": self._default_image_count,
            "grid_columns": self._default_grid_columns,
        }
