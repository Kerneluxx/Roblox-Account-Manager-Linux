import hashlib
import shutil
from pathlib import Path

from . import config
from .errors import ManagerError, SessionError
from .fsutil import ensure_private_dir, read_limited, write_private
from .validation import ID_RE

BACKUP_LABEL = "backup"


class SessionStore:
    def __init__(self, vault, sessions_dir, sober_root, session_files):
        self._vault = vault
        self._sessions = Path(sessions_dir)
        self._root = Path(sober_root)
        self._files = tuple(self._relative(item) for item in session_files)

    @staticmethod
    def _relative(item):
        path = Path(item)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise SessionError("err_session_path")
        return path

    def _live(self, rel):
        current = self._root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise SessionError("err_symlink")
        return current

    def _directory(self, label):
        if label != BACKUP_LABEL and not ID_RE.fullmatch(label):
            raise SessionError("err_account_id")
        return self._sessions / label

    @staticmethod
    def _blob(directory, rel):
        digest = hashlib.sha256(rel.as_posix().encode("utf-8")).hexdigest()[:24]
        return directory / f"{digest}.bin"

    def _capture_to(self, directory):
        saved = 0
        for rel in self._files:
            live = self._live(rel)
            if not live.is_file():
                continue
            if saved == 0:
                ensure_private_dir(self._sessions)
                ensure_private_dir(directory)
            try:
                data = read_limited(live, config.MAX_SESSION_BYTES)
            except OSError as exc:
                raise SessionError("err_session_read", why=exc.strerror or "") from exc
            write_private(self._blob(directory, rel), self._vault.encrypt(data))
            saved += 1
        return saved

    def live_exists(self):
        return any(self._live(rel).is_file() for rel in self._files)

    def has_snapshot(self, label):
        directory = self._directory(label)
        return any(self._blob(directory, rel).is_file() for rel in self._files)

    def capture(self, label):
        return self._capture_to(self._directory(label))

    def backup_live(self):
        return self._capture_to(self._directory(BACKUP_LABEL))

    def restore(self, label):
        directory = self._directory(label)
        restored = 0
        for rel in self._files:
            blob = self._blob(directory, rel)
            live = self._live(rel)
            if blob.is_file():
                try:
                    token = read_limited(blob, config.MAX_SESSION_BYTES * 2)
                except (OSError, ManagerError) as exc:
                    raise SessionError("err_session_read", why=str(exc)) from exc
                write_private(live, self._vault.decrypt(token))
                restored += 1
            elif live.exists():
                live.unlink()
        return restored

    def delete(self, label):
        directory = self._directory(label)
        if directory.is_dir() and not directory.is_symlink():
            shutil.rmtree(directory)
