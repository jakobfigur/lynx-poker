"""Laden versionierter Tischprofile."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_PROFILE = "pokerth_web_v1.json"


class Profile:
    def __init__(self, data: dict[str, Any], path: str):
        self.data = data
        self.path = path
        self.name = data["name"]
        self.version = data["version"]

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"

    def __getitem__(self, key):
        return self.data[key]

    def hsv(self, *keys) -> tuple[np.ndarray, np.ndarray]:
        d = self.data
        for k in keys:
            d = d[k]
        return np.array(d["lo"], np.uint8), np.array(d["hi"], np.uint8)

    @staticmethod
    def load(path: str | Path | None = None) -> "Profile":
        if path is None:
            text = resources.files("pokercollector.profiles").joinpath(DEFAULT_PROFILE).read_text("utf-8")
            return Profile(json.loads(text), f"builtin:{DEFAULT_PROFILE}")
        p = Path(path)
        return Profile(json.loads(p.read_text("utf-8")), str(p))
