import json
import os
import shutil
from pathlib import Path

from . import config
from .errors import ManagerError
from .fsutil import read_limited
from .validation import ID_RE, clean_text
from .vault import Vault

FILES = (
    config.VAULT_FILE.name,
    config.SETTINGS_FILE.name,
    config.SETTINGS_FILE.with_suffix(".corrupt").name,
    config.STATE_FILE.name,
    config.LEGACY_FILE.name,
    config.LEGACY_FILE.with_suffix(".corrupt").name,
    config.LEGACY_FILE.name + ".migrado",
    config.LOG_FILE.name,
    config.LOG_FILE.name + ".1",
    config.LOG_FILE.name + ".2",
)
DIRECTORIES = (
    config.PROFILES_DIR.name,
    config.SESSIONS_DIR.name,
    config.EXPORTS_DIR.name,
)


def wipe_all(base):
    base = Path(base)
    for name in DIRECTORIES:
        path = base / name
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
    for name in FILES:
        try:
            (base / name).unlink()
        except FileNotFoundError:
            pass


def read_legacy(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        raw = json.loads(read_limited(path, 2_000_000).decode("utf-8"))
    except (OSError, ValueError, ManagerError):
        return None
    if not isinstance(raw, dict):
        return None
    accounts = []
    items = raw.get("accounts")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            continue
        accounts.append(
            {
                "id": ident,
                "username": clean_text(item.get("alias")) or "?",
                "group": clean_text(item.get("group")),
                "notes": clean_text(item.get("notes"), 120),
                "last_launch": clean_text(item.get("last_launch"), 20),
            }
        )
    settings = raw.get("settings")
    return (settings if isinstance(settings, dict) else {}), accounts


def migrate_legacy(vault, path):
    legacy = read_legacy(path)
    if legacy is None:
        return 0
    count = 0
    for raw in legacy[1]:
        if vault.adopt(raw) is not None:
            count += 1
    return count


def retire_legacy(path):
    path = Path(path)
    try:
        os.replace(path, path.with_name(path.name + ".migrado"))
    except OSError:
        pass


def create_vault(vault_path, password, legacy_path):
    vault = Vault.create(vault_path, password)
    migrated = migrate_legacy(vault, legacy_path)
    vault.save()
    if migrated:
        retire_legacy(legacy_path)
    return vault, migrated
