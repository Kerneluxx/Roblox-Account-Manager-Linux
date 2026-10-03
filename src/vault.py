import base64
import binascii
import hmac
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from . import config
from .errors import VaultError, WrongPassword
from .fsutil import write_private
from .validation import (
    ID_RE,
    clean_text,
    validate_master,
    validate_password,
    validate_username,
)

FORMAT_VERSION = 2
SALT_LENGTH = 16
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


def _derive(password, salt):
    kdf = Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _wrap(password, salt, data_key):
    return Fernet(_derive(password, salt)).encrypt(data_key)


def new_id(taken):
    while True:
        value = os.urandom(6).hex()
        if value not in taken:
            return value


def _record(raw):
    if not isinstance(raw, dict):
        return None
    ident = raw.get("id")
    if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
        return None
    password = raw.get("password")
    return {
        "id": ident,
        "username": clean_text(raw.get("username")) or "?",
        "password": password if isinstance(password, str) else "",
        "group": clean_text(raw.get("group")),
        "notes": clean_text(raw.get("notes"), 120),
        "last_launch": clean_text(raw.get("last_launch"), 20),
    }


def _records_from_payload(version, payload):
    if version == 1:
        if not isinstance(payload, dict):
            raise VaultError("err_vault_content")
        records = {}
        for name, password in payload.items():
            if not isinstance(name, str) or not isinstance(password, str):
                raise VaultError("err_vault_content")
            ident = new_id(records)
            records[ident] = _record(
                {"id": ident, "username": name, "password": password}
            )
        return records
    if not isinstance(payload, dict) or not isinstance(payload.get("accounts"), list):
        raise VaultError("err_vault_content")
    records = {}
    for raw in payload["accounts"][: config.MAX_ACCOUNTS]:
        item = _record(raw)
        if item is not None and item["id"] not in records:
            records[item["id"]] = item
    return records


class Vault:
    def __init__(self, path, data_key, salt, wrapped, records):
        self._path = Path(path)
        self._data_key = data_key
        self._fernet = Fernet(data_key)
        self._salt = salt
        self._wrapped = wrapped
        self._records = dict(records)

    @property
    def path(self):
        return self._path

    @classmethod
    def create(cls, path, password):
        path = Path(path)
        if path.exists():
            raise VaultError("err_vault_exists")
        validate_master(password)
        salt = os.urandom(SALT_LENGTH)
        data_key = Fernet.generate_key()
        return cls(path, data_key, salt, _wrap(password, salt, data_key), {})

    @classmethod
    def open(cls, path, password):
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            version = raw["version"]
            if version not in (1, FORMAT_VERSION):
                raise VaultError("err_vault_version")
            salt = base64.b64decode(raw["salt"], validate=True)
            wrapped = raw["key"].encode("ascii")
            body = raw["accounts"].encode("ascii")
        except VaultError:
            raise
        except (OSError, ValueError, KeyError, TypeError, AttributeError, binascii.Error) as exc:
            raise VaultError("err_vault_corrupt") from exc
        try:
            data_key = Fernet(_derive(password, salt)).decrypt(wrapped)
        except InvalidToken as exc:
            raise WrongPassword("err_wrong_master") from exc
        try:
            payload = json.loads(Fernet(data_key).decrypt(body))
        except (InvalidToken, ValueError) as exc:
            raise VaultError("err_vault_corrupt") from exc
        return cls(path, data_key, salt, wrapped, _records_from_payload(version, payload))

    def verify(self, password):
        try:
            candidate = Fernet(_derive(password, self._salt)).decrypt(self._wrapped)
        except InvalidToken:
            return False
        return hmac.compare_digest(candidate, self._data_key)

    def save(self):
        payload = {"accounts": [self._records[key] for key in self._records]}
        body = {
            "version": FORMAT_VERSION,
            "salt": base64.b64encode(self._salt).decode("ascii"),
            "key": self._wrapped.decode("ascii"),
            "accounts": self._fernet.encrypt(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            ).decode("ascii"),
        }
        write_private(self._path, json.dumps(body).encode("utf-8"))

    def change_password(self, new_password):
        validate_master(new_password)
        salt = os.urandom(SALT_LENGTH)
        self._wrapped = _wrap(new_password, salt, self._data_key)
        self._salt = salt

    def encrypt(self, data):
        return self._fernet.encrypt(data)

    def decrypt(self, token):
        try:
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise VaultError("err_crypto") from exc

    def __len__(self):
        return len(self._records)

    def all(self):
        ordered = sorted(self._records.values(), key=lambda item: item["username"].lower())
        return [dict(item) for item in ordered]

    def get(self, ident):
        item = self._records.get(ident)
        return dict(item) if item else None

    def find(self, username):
        wanted = username.strip().lower() if isinstance(username, str) else ""
        for item in self._records.values():
            if item["username"].lower() == wanted:
                return dict(item)
        return None

    def _require(self, ident):
        item = self._records.get(ident)
        if item is None:
            raise VaultError("err_not_found")
        return item

    def add(self, username, password="", group="", notes="", overwrite=False):
        username = validate_username(username)
        validate_password(password)
        existing = self.find(username)
        if existing is not None:
            if not overwrite:
                return "exists", existing
            item = self._records[existing["id"]]
            item["password"] = password
            return "updated", dict(item)
        if len(self._records) >= config.MAX_ACCOUNTS:
            raise VaultError("err_limit", n=config.MAX_ACCOUNTS)
        ident = new_id(self._records)
        item = _record(
            {
                "id": ident,
                "username": username,
                "password": password,
                "group": group,
                "notes": notes,
            }
        )
        self._records[ident] = item
        return "added", dict(item)

    def adopt(self, raw):
        item = _record(raw)
        if item is None or item["id"] in self._records:
            return None
        if len(self._records) >= config.MAX_ACCOUNTS:
            return None
        base = item["username"]
        candidate, counter = base, 1
        while self.find(candidate) is not None:
            counter += 1
            suffix = f"_{counter}"
            candidate = base[: 60 - len(suffix)] + suffix
        item["username"] = candidate
        self._records[item["id"]] = item
        return dict(item)

    def update(self, ident, username=None, password=None, group=None, notes=None):
        item = self._require(ident)
        if username is not None:
            username = validate_username(username)
            other = self.find(username)
            if other is not None and other["id"] != ident:
                raise VaultError("err_exists", name=username)
            item["username"] = username
        if password is not None:
            item["password"] = validate_password(password)
        if group is not None:
            item["group"] = clean_text(group)
        if notes is not None:
            item["notes"] = clean_text(notes, 120)
        return dict(item)

    def touch(self, ident, stamp):
        self._require(ident)["last_launch"] = clean_text(stamp, 20)

    def remove(self, ident):
        item = self._require(ident)
        del self._records[ident]
        return dict(item)
