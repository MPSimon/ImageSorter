from enum import Enum


class Label(str, Enum):
    GOOD = "good"
    REGENERATE = "regenerate"
    UPSCALE = "upscale"
    BAD = "bad"

