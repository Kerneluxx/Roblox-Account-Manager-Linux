import tempfile
import unittest
from pathlib import Path

from src import importer
from src.errors import ValidationError
from src.vault import Vault

SAMPLE = """Usuario:Senha

PlayerOne:Passw0rd!
PlayerTwo:
IlllIIIIllIIIlll7:a:b:c
broken line
x:short
Player_Three:  spaced  
playerone:duplicate
"""


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Vault.create(Path(self.tmp.name) / "v.json", "master-password")

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse(self):
        result = importer.parse_accounts(SAMPLE)
        users = [user for user, _ in result.entries]
        self.assertEqual(
            users,
            ["PlayerOne", "PlayerTwo", "IlllIIIIllIIIlll7", "Player_Three", "playerone"],
        )
        passwords = dict(result.entries)
        self.assertEqual(passwords["PlayerTwo"], "")
        self.assertEqual(passwords["IlllIIIIllIIIlll7"], "a:b:c")
        self.assertEqual(passwords["Player_Three"], "spaced")
        self.assertEqual([number for number, _ in result.invalid], [6, 7])

    def test_apply_and_overwrite(self):
        entries = importer.parse_accounts(SAMPLE).entries
        report = importer.apply(self.vault, entries)
        self.assertEqual((report.added, report.updated, report.skipped, report.duplicated), (4, 0, 0, 1))
        report = importer.apply(self.vault, [("PlayerOne", "new")], overwrite=False)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(self.vault.get_password("PlayerOne"), "Passw0rd!")
        importer.apply(self.vault, [("PlayerOne", "new")], overwrite=True)
        self.assertEqual(self.vault.get_password("PlayerOne"), "new")

    def test_export_roundtrip(self):
        importer.apply(self.vault, importer.parse_accounts(SAMPLE).entries)
        text = importer.export_text(self.vault)
        again = importer.parse_accounts(text)
        self.assertEqual(again.invalid, [])
        self.assertEqual(sorted(again.entries), sorted(
            (name, self.vault.get_password(name)) for name in self.vault.names()
        ))

    def test_load_file_rejects_bad_input(self):
        folder = Path(self.tmp.name)
        binary = folder / "bin.txt"
        binary.write_bytes(b"\xff\xfe\x00\x01")
        with self.assertRaises(ValidationError):
            importer.load_file(binary)
        with self.assertRaises(ValidationError):
            importer.load_file(folder / "missing.txt")
        with self.assertRaises(ValidationError):
            importer.load_file(folder)

    def test_bom_is_accepted(self):
        path = Path(self.tmp.name) / "bom.txt"
        path.write_bytes("\ufeffPlayerOne:abc\n".encode("utf-8"))
        self.assertEqual(importer.load_file(path).entries, [("PlayerOne", "abc")])


if __name__ == "__main__":
    unittest.main()
