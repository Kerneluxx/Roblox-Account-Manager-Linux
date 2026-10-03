from dataclasses import dataclass, field

from . import config
from .errors import ManagerError, ValidationError
from .fsutil import read_limited
from .validation import validate_password, validate_username

HEADERS = {"usuario:senha", "usuário:senha", "user:password", "username:password"}


@dataclass
class ParseResult:
    entries: list = field(default_factory=list)
    invalid: list = field(default_factory=list)


@dataclass
class ImportReport:
    added: int = 0
    updated: int = 0
    skipped: int = 0
    duplicated: int = 0


def parse_accounts(text):
    result = ParseResult()
    for number, raw in enumerate(text.splitlines(), start=1):
        if number > config.MAX_IMPORT_LINES:
            raise ValidationError("err_import_lines", n=config.MAX_IMPORT_LINES)
        line = raw.strip()
        if not line or line.lower().replace(" ", "") in HEADERS:
            continue
        user, separator, password = line.partition(":")
        if not separator:
            result.invalid.append((number, "err_import_format"))
            continue
        try:
            result.entries.append((validate_username(user), validate_password(password.strip())))
        except ValidationError as exc:
            result.invalid.append((number, exc.key))
    return result


def parse_bytes(data):
    try:
        return parse_accounts(data.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValidationError("err_import_utf8") from exc


def load_file(path):
    try:
        data = read_limited(path, config.MAX_IMPORT_BYTES)
    except OSError as exc:
        raise ValidationError("err_import_read", why=exc.strerror or type(exc).__name__) from exc
    return parse_bytes(data)


def parse_text(text):
    data = text.encode("utf-8")
    if len(data) > config.MAX_IMPORT_BYTES:
        raise ValidationError("err_too_big")
    return parse_bytes(data)


def conflicts(vault, entries):
    return sum(1 for user, _ in entries if vault.find(user) is not None)


def apply(vault, entries, overwrite=False):
    report = ImportReport()
    seen = set()
    for user, password in entries:
        key = user.lower()
        if key in seen:
            report.duplicated += 1
            continue
        seen.add(key)
        existing = vault.find(user)
        force = overwrite or (existing is not None and not existing["password"] and bool(password))
        try:
            outcome, _ = vault.add(user, password, overwrite=force)
        except ManagerError:
            report.skipped += 1
            continue
        if outcome == "added":
            report.added += 1
        elif outcome == "updated":
            report.updated += 1
        else:
            report.skipped += 1
    return report


def export_text(vault):
    lines = [f"{item['username']}:{item['password']}" for item in vault.all()]
    return "\n".join(lines) + ("\n" if lines else "")
