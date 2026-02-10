import json
from pathlib import Path
from typing import Any, Dict

from imagesorter.domain.settings import Settings


class SettingsStore:
    def __init__(self, path: Path):
        self._path = path

    def load(self) -> Settings:
        if self._path.exists():
            data = json.loads(self._path.read_text())
            if isinstance(data, dict):
                return Settings.from_dict(data)
        return Settings.from_dict({})

    def save(self, settings: Settings) -> None:
        data: Dict[str, Any] = settings.to_public_dict()
        self._path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

