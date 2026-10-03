import tempfile
import unittest
from pathlib import Path

from src.errors import SessionError, ValidationError
from src.sessions import SessionStore
from src.vault import Vault


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "sober"
        (self.root / "data" / "sober").mkdir(parents=True)
        self.cookie = self.root / "data" / "sober" / "cookies"
        self.vault = Vault.create(base / "v.json", "master-password")
        self.store = SessionStore(self.vault, base / "sessions", self.root, ("data/sober/cookies",))

    def tearDown(self):
        self.tmp.cleanup()

    def test_capture_restore_isolated_and_encrypted(self):
        self.cookie.write_bytes(b"token-A")
        self.assertEqual(self.store.capture("PlayerOne"), 1)
        self.cookie.write_bytes(b"token-B")
        self.store.capture("PlayerTwo")
        self.store.restore("PlayerOne")
        self.assertEqual(self.cookie.read_bytes(), b"token-A")
        self.store.restore("PlayerTwo")
        self.assertEqual(self.cookie.read_bytes(), b"token-B")
        stored = b"".join(p.read_bytes() for p in (Path(self.tmp.name) / "sessions").rglob("*.bin"))
        self.assertNotIn(b"token-A", stored)
        self.assertNotIn(b"token-B", stored)

    def test_restore_without_snapshot_clears_live(self):
        self.cookie.write_bytes(b"token-A")
        self.store.restore("PlayerNew")
        self.assertFalse(self.cookie.exists())

    def test_backup_live(self):
        self.cookie.write_bytes(b"token-A")
        self.assertEqual(self.store.backup_live(), 1)

    def test_delete(self):
        self.cookie.write_bytes(b"token-A")
        self.store.capture("PlayerOne")
        self.assertTrue(self.store.has_snapshot("PlayerOne"))
        self.store.delete("PlayerOne")
        self.assertFalse(self.store.has_snapshot("PlayerOne"))

    def test_rejects_path_traversal(self):
        for bad in ("../x", "a/b", ".."):
            with self.assertRaises(ValidationError):
                self.store.capture(bad)
        with self.assertRaises(SessionError):
            SessionStore(self.vault, self.root, self.root, ("../escape",))
        with self.assertRaises(SessionError):
            SessionStore(self.vault, self.root, self.root, ("/etc/passwd",))

    def test_rejects_symlinks(self):
        target = Path(self.tmp.name) / "outside"
        target.write_bytes(b"secret")
        self.cookie.symlink_to(target)
        with self.assertRaises(SessionError):
            self.store.capture("PlayerOne")
        with self.assertRaises(SessionError):
            self.store.restore("PlayerOne")


if __name__ == "__main__":
    unittest.main()
