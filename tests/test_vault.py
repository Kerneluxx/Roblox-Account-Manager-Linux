import json
import stat
import tempfile
import unittest
from pathlib import Path

from src.errors import ValidationError, VaultError, WrongPassword
from src.vault import Vault


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vault.json"

    def tearDown(self):
        self.tmp.cleanup()

    def make(self):
        vault = Vault.create(self.path, "master-password")
        vault.save()
        return vault

    def test_roundtrip(self):
        vault = self.make()
        vault.add("PlayerOne", "pw:with:colons")
        vault.add("PlayerTwo", "")
        vault.save()
        reopened = Vault.open(self.path, "master-password")
        self.assertEqual(reopened.names(), ["PlayerOne", "PlayerTwo"])
        self.assertEqual(reopened.get_password("playerone"), "pw:with:colons")
        self.assertEqual(reopened.get_password("PlayerTwo"), "")

    def test_wrong_password(self):
        self.make()
        with self.assertRaises(WrongPassword):
            Vault.open(self.path, "not-the-password")

    def test_file_is_encrypted_and_private(self):
        vault = self.make()
        vault.add("PlayerOne", "very-secret-value")
        vault.save()
        raw = self.path.read_text()
        self.assertNotIn("very-secret-value", raw)
        self.assertNotIn("PlayerOne", raw)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_tampering_detected(self):
        vault = self.make()
        vault.add("PlayerOne", "x")
        vault.save()
        body = json.loads(self.path.read_text())
        body["accounts"] = body["accounts"][:-4] + "AAAA"
        self.path.write_text(json.dumps(body))
        with self.assertRaises(VaultError):
            Vault.open(self.path, "master-password")

    def test_corrupt_file(self):
        self.path.write_text("not json")
        with self.assertRaises(VaultError):
            Vault.open(self.path, "master-password")

    def test_change_master_password(self):
        vault = self.make()
        vault.add("PlayerOne", "abc")
        vault.change_password("another-master")
        vault.save()
        with self.assertRaises(WrongPassword):
            Vault.open(self.path, "master-password")
        self.assertEqual(Vault.open(self.path, "another-master").get_password("PlayerOne"), "abc")

    def test_validation(self):
        vault = self.make()
        for bad in ("ab", "a" * 21, "../etc", "with space", "bad:name", ""):
            with self.assertRaises(ValidationError):
                vault.add(bad, "x")
        with self.assertRaises(ValidationError):
            vault.add("PlayerOne", "line\nbreak")
        with self.assertRaises(ValidationError):
            Vault.create(Path(self.tmp.name) / "other.json", "short")

    def test_duplicates_case_insensitive(self):
        vault = self.make()
        self.assertEqual(vault.add("PlayerOne", "a"), "added")
        self.assertEqual(vault.add("playerone", "b"), "exists")
        self.assertEqual(vault.add("PLAYERONE", "b", overwrite=True), "updated")
        self.assertEqual(vault.names(), ["PlayerOne"])
        self.assertEqual(vault.get_password("PlayerOne"), "b")

    def test_remove(self):
        vault = self.make()
        vault.add("PlayerOne", "a")
        self.assertEqual(vault.remove("playerone"), "PlayerOne")
        with self.assertRaises(VaultError):
            vault.remove("PlayerOne")


if __name__ == "__main__":
    unittest.main()
