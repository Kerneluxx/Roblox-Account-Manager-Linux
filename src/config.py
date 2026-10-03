import os
from pathlib import Path

APP_NAME = "gerenciador-contas-roblox"
APP_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = APP_ROOT / "version.txt"


def _config_dir():
    env = os.environ.get("GCR_DIR")
    if env and os.path.isabs(env):
        return Path(os.path.realpath(env))
    return Path.home() / ".config" / APP_NAME


CONFIG_DIR = _config_dir()
VAULT_FILE = CONFIG_DIR / "cofre.json"
SETTINGS_FILE = CONFIG_DIR / "config.json"
STATE_FILE = CONFIG_DIR / "estado.json"
LEGACY_FILE = CONFIG_DIR / "contas.json"
PROFILES_DIR = CONFIG_DIR / "perfis"
SESSIONS_DIR = CONFIG_DIR / "sessoes"
EXPORTS_DIR = CONFIG_DIR / "exportacoes"
LOG_FILE = CONFIG_DIR / "app.log"

SOBER_APP_ID = "org.vinegarhq.Sober"
SOBER_ROOT = Path.home() / ".var" / "app" / SOBER_APP_ID
SESSION_FILES = ("data/sober/cookies",)

MAX_ACCOUNTS = 2000
MAX_IMPORT_BYTES = 1_048_576
MAX_IMPORT_LINES = 10_000
MAX_SESSION_BYTES = 5 * 1024 * 1024
MAX_SETTINGS_BYTES = 200_000
CLIPBOARD_SECONDS = 30
MAX_UNLOCK_ATTEMPTS = 3


def read_version():
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "?"
    except OSError:
        return "?"
