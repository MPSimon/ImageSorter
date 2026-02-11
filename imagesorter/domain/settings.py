from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

from imagesorter.domain.labels import Label


@dataclass(frozen=True)
class Settings:
    input_dir: str
    image_count: int
    image_size: int
    grid_columns: int
    label_dirs: Dict[str, str]
    labels: List[str]
    click_layout: str

    @staticmethod
    def from_dict(d: Mapping[str, Any]) -> "Settings":
        input_dir = str(d.get("input_dir") or "input")
        image_count = int(d.get("image_count") or 20)
        image_size = int(d.get("image_size") or 200)
        grid_columns = int(d.get("grid_columns") or 5)

        label_dirs = dict(d.get("label_dirs") or {})
        good_dir = d.get("good_dir")
        bad_dir = d.get("bad_dir")
        if good_dir and "good" not in label_dirs:
            label_dirs["good"] = str(good_dir)
        if bad_dir and "bad" not in label_dirs:
            label_dirs["bad"] = str(bad_dir)

        labels = d.get("labels")
        if not isinstance(labels, list) or not labels:
            labels = [Label.GOOD.value, Label.REGENERATE.value, Label.UPSCALE.value, Label.BAD.value]
        labels = [str(x) for x in labels]

        click_layout = str(d.get("click_layout") or "quadrants")

        return Settings(
            input_dir=input_dir,
            image_count=image_count,
            image_size=image_size,
            grid_columns=grid_columns,
            label_dirs=label_dirs,
            labels=labels,
            click_layout=click_layout,
        )

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "input_dir": self.input_dir,
            "image_count": self.image_count,
            "image_size": self.image_size,
            "grid_columns": self.grid_columns,
            "label_dirs": dict(self.label_dirs),
            "labels": list(self.labels),
            "click_layout": self.click_layout,
        }

