import json
import os
import time
from pathlib import Path

from . import config
from .fsutil import write_private
from .idiomas import LANGS
from .validation import PLACE_RE, command_problem

CLIENT_CUSTOM = "Personalizado"
CLIENTS = {
    "Sober (Flatpak)": "flatpak run org.vinegarhq.Sober {uri}",
    "Mocktail (instalação nativa)": "mocktail {uri}",
    "Mocktail (Flatpak)": "flatpak run space.bigrat.mocktail {uri}",
    CLIENT_CUSTOM: "",
}
DEFAULT_CLIENT = "Sober (Flatpak)"
SWAP_CLIENT = "Sober (Flatpak)"
FONT_SCALES = {"small": 0.9, "normal": 1.0, "large": 1.25, "xlarge": 1.5}
THEMES = ["system", "light", "dark", "hc_dark", "hc_light"]
LANG_CHOICES = ["auto"] + list(LANGS)

DEFAULTS = {
    "client": DEFAULT_CLIENT,
    "launch_command": CLIENTS[DEFAULT_CLIENT],
    "allow_custom": False,
    "isolate_profiles": True,
    "language": "auto",
    "font": "normal",
    "theme": "system",
    "max_batch": 8,
    "idle_lock_minutes": 5,
    "seen_guide": False,
    "last_place": "",
    "fails": 0,
    "until": 0.0,
}


def sanitize(raw):
    data = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return data

    def pick(key, allowed):
        value = raw.get(key)
        if isinstance(value, str) and value in allowed:
            data[key] = value

    pick("client", CLIENTS)
    pick("language", LANG_CHOICES)
    pick("font", FONT_SCALES)
    pick("theme", THEMES)
    for key in ("allow_custom", "isolate_profiles", "seen_guide"):
        if isinstance(raw.get(key), bool):
            data[key] = raw[key]
    for key, low, high in (("max_batch", 1, 20), ("idle_lock_minutes", 0, 120)):
        value = raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high:
            data[key] = value
    place = raw.get("last_place")
    if isinstance(place, str) and PLACE_RE.fullmatch(place):
        data["last_place"] = place
    fails, until = raw.get("fails"), raw.get("until")
    if isinstance(fails, int) and not isinstance(fails, bool) and 0 <= fails < 1000:
        data["fails"] = fails
    if isinstance(until, (int, float)) and not isinstance(until, bool) and until >= 0:
        data["until"] = float(until)
    if data["client"] == CLIENT_CUSTOM:
        command = raw.get("launch_command")
        if data["allow_custom"] and command_problem(command) is None:
            data["launch_command"] = command
        else:
            data["client"] = DEFAULT_CLIENT
            data["launch_command"] = CLIENTS[DEFAULT_CLIENT]
    else:
        data["launch_command"] = CLIENTS[data["client"]]
    return data


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else config.SETTINGS_FILE
        self.data = sanitize(None)
        self.warning = None
        self.loaded = False
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            if self.path.stat().st_size > config.MAX_SETTINGS_BYTES:
                raise ValueError
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError
        except (OSError, ValueError):
            try:
                os.replace(self.path, self.path.with_suffix(".corrupt"))
            except OSError:
                pass
            self.warning = "log_settings_corrupt"
            return
        self.data = sanitize(raw)
        self.loaded = True

    def replace(self, raw):
        self.data = sanitize(raw)

    def save(self):
        write_private(self.path, json.dumps(self.data, indent=2, ensure_ascii=False).encode("utf-8"))

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def update(self, **values):
        self.data.update(values)

    def wait_seconds(self):
        return max(0, int(self.data["until"] - time.time()))

    def register_success(self):
        self.data["fails"], self.data["until"] = 0, 0.0
        self.save()

    def register_failure(self):
        self.data["fails"] += 1
        fails = self.data["fails"]
        if fails >= config.MAX_UNLOCK_ATTEMPTS:
            delay = min(30 * 2 ** (fails - config.MAX_UNLOCK_ATTEMPTS), 900)
            self.data["until"] = time.time() + delay
        self.save()
        return self.wait_seconds()
