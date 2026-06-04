"""Config manager — read/write settings.json and manage templates directory."""

import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "threshold": 0.8,
    "baseline_width": 0,
    "baseline_height": 0,
    "actions": [],
    "round_interval": 10,
    "wake_delay": 3,
    "screen_off_delay": 0,
    "window_geometry": {"x": 100, "y": 100, "collapsed": False},
}


class ConfigManager:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.config_path = self.base_dir / "settings.json"
        self._data = self._load()

    def _load(self) -> dict:
        if not self.config_path.exists():
            self._data = dict(DEFAULT_CONFIG)
            self.save()
            return self._data
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            self._data = dict(DEFAULT_CONFIG)
            self.save()
            return self._data

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    @property
    def interval_sec(self) -> int:
        return self._data.get("interval_sec", 5)

    @interval_sec.setter
    def interval_sec(self, value: int):
        self._data["interval_sec"] = max(1, int(value))
        self.save()

    @property
    def round_interval(self) -> int:
        return self._data.get("round_interval", 10)

    @round_interval.setter
    def round_interval(self, value: int):
        self._data["round_interval"] = max(1, int(value))
        self.save()

    @property
    def wake_delay(self) -> int:
        return self._data.get("wake_delay", 3)

    @wake_delay.setter
    def wake_delay(self, value: int):
        self._data["wake_delay"] = max(0, int(value))
        self.save()

    @property
    def screen_off_delay(self) -> int:
        return self._data.get("screen_off_delay", 0)

    @screen_off_delay.setter
    def screen_off_delay(self, value: int):
        self._data["screen_off_delay"] = max(0, int(value))
        self.save()

    @property
    def threshold(self) -> float:
        return self._data.get("threshold", 0.8)

    @threshold.setter
    def threshold(self, value: float):
        self._data["threshold"] = max(0.1, min(1.0, float(value)))
        self.save()

    @property
    def actions(self) -> list:
        return self._data.get("actions", [])

    def set_actions(self, actions: list):
        self._data["actions"] = list(actions)
        self.save()

    def add_action(self, name: str, template_file: str, post_delay: float = 2.0):
        self._data["actions"].append({
            "name": name, "template": template_file, "post_delay": post_delay,
        })
        self.save()

    def remove_action(self, index: int):
        if 0 <= index < len(self._data["actions"]):
            del self._data["actions"][index]
            self.save()

    def update_action(self, index: int, **kwargs):
        if 0 <= index < len(self._data["actions"]):
            for k, v in kwargs.items():
                self._data["actions"][index][k] = v
            self.save()

    def clear_actions(self):
        self._data["actions"] = []
        self.save()

    @property
    def baseline_resolution(self) -> tuple:
        return (self._data.get("baseline_width", 0), self._data.get("baseline_height", 0))

    @baseline_resolution.setter
    def baseline_resolution(self, wh: tuple):
        self._data["baseline_width"], self._data["baseline_height"] = wh
        self.save()

    @property
    def collapsed(self) -> bool:
        return self._data.get("window_geometry", {}).get("collapsed", False)

    @collapsed.setter
    def collapsed(self, value: bool):
        self._data.setdefault("window_geometry", {})["collapsed"] = bool(value)
        self.save()

    @property
    def window_pos(self) -> tuple:
        g = self._data.get("window_geometry", {})
        return (g.get("x", 100), g.get("y", 100))

    @window_pos.setter
    def window_pos(self, xy: tuple):
        self._data.setdefault("window_geometry", {})["x"] = xy[0]
        self._data.setdefault("window_geometry", {})["y"] = xy[1]
        self.save()
