import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from src import importer, storage
from src.errors import ManagerError, ValidationError, VaultError, WrongPassword
from src.idiomas import LANGS
from src.launcher import Launcher, build_command, game_uri
from src.sessions import SessionStore
from src.settings import Settings, sanitize
from src.validation import command_problem
from src.vault import Vault

SAMPLE = """Usuario:Senha

SpiderNoirisCool1:Oxossi1511!
InsecureKasparan:123123123Andrew1
saulodasi04:Oxossi1411!!
AndrewDcsds:
IlllIIIIllIIIlll7:Oxossi1411!
IIIIlllllllIlIlIl47:Oxossi1411!
MelhorDeGaia1:Oxossi1411!
IIIIlIIllI4:Oxossi1411!
IIIlllIIIllI82:Oxossi1411!
IIIllllIIllIIlIIll21:Oxossi1411!
IllllIIIlIIllI3:Oxossi1411!
IlllIIIIIlllI_3:Oxossi1411!
MelhorDeGaia8:Ogum1511!
MelhorDeGaia4:
MelhorDeGaia6:Oxossi1411!
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.vault = Vault.create(self.dir / "cofre.json", "senha-mestra-1")

    def tearDown(self):
        self.tmp.cleanup()


class VaultTests(Base):
    def test_roundtrip_and_permissions(self):
        self.vault.add("Alpha_1", "segredo", group="g", notes="n")
        self.vault.save()
        mode = stat.S_IMODE(os.stat(self.vault.path).st_mode)
        self.assertEqual(mode, 0o600)
        reopened = Vault.open(self.vault.path, "senha-mestra-1")
        self.assertEqual(reopened.find("alpha_1")["password"], "segredo")
        self.assertNotIn("segredo", self.vault.path.read_text())

    def test_wrong_password(self):
        self.vault.save()
        with self.assertRaises(WrongPassword):
            Vault.open(self.vault.path, "errada-errada")

    def test_change_master(self):
        self.vault.add("Alpha_1", "x")
        self.vault.change_password("outra-senha-9")
        self.vault.save()
        with self.assertRaises(WrongPassword):
            Vault.open(self.vault.path, "senha-mestra-1")
        self.assertEqual(len(Vault.open(self.vault.path, "outra-senha-9")), 1)

    def test_short_master_rejected(self):
        with self.assertRaises(ValidationError):
            Vault.create(self.dir / "x.json", "curta")

    def test_duplicates_case_insensitive(self):
        self.vault.add("Alpha_1", "a")
        outcome, _ = self.vault.add("ALPHA_1", "b")
        self.assertEqual(outcome, "exists")
        self.assertEqual(self.vault.find("alpha_1")["password"], "a")

    def test_invalid_names(self):
        for bad in ("ab", "x" * 21, "com espaco", "../etc", "añb"):
            with self.assertRaises(ValidationError):
                self.vault.add(bad, "")

    def test_tampered_file(self):
        self.vault.save()
        data = json.loads(self.vault.path.read_text())
        data["accounts"] = data["accounts"][:-4] + "AAAA"
        self.vault.path.write_text(json.dumps(data))
        with self.assertRaises(VaultError):
            Vault.open(self.vault.path, "senha-mestra-1")

    def test_verify(self):
        self.assertTrue(self.vault.verify("senha-mestra-1"))
        self.assertFalse(self.vault.verify("nada-nada-1"))

    def test_update_rename_conflict(self):
        _, first = self.vault.add("Alpha_1", "")
        self.vault.add("Beta_2", "")
        with self.assertRaises(VaultError):
            self.vault.update(first["id"], username="beta_2")


class ImportTests(Base):
    def test_sample_list(self):
        parsed = importer.parse_accounts(SAMPLE)
        self.assertEqual(parsed.invalid, [])
        self.assertEqual(len(parsed.entries), 15)
        report = importer.apply(self.vault, parsed.entries)
        self.assertEqual(report.added, 15)
        self.assertEqual(self.vault.find("AndrewDcsds")["password"], "")
        self.assertEqual(self.vault.find("saulodasi04")["password"], "Oxossi1411!!")

    def test_export_roundtrip(self):
        importer.apply(self.vault, importer.parse_accounts(SAMPLE).entries)
        text = importer.export_text(self.vault)
        again = importer.parse_accounts(text)
        self.assertEqual(len(again.entries), 15)
        self.assertEqual(
            {u.lower(): p for u, p in again.entries},
            {u.lower(): p for u, p in importer.parse_accounts(SAMPLE).entries},
        )

    def test_password_with_colon_and_invalid_lines(self):
        parsed = importer.parse_accounts("abc_1:a:b:c\nsemseparador\nx:y\n")
        self.assertEqual(parsed.entries, [("abc_1", "a:b:c")])
        self.assertEqual([n for n, _ in parsed.invalid], [2, 3])

    def test_existing_kept_unless_overwrite(self):
        self.vault.add("Alpha_1", "antiga")
        importer.apply(self.vault, [("Alpha_1", "nova")])
        self.assertEqual(self.vault.find("Alpha_1")["password"], "antiga")
        importer.apply(self.vault, [("Alpha_1", "nova")], overwrite=True)
        self.assertEqual(self.vault.find("Alpha_1")["password"], "nova")

    def test_empty_password_filled_by_import(self):
        self.vault.add("Alpha_1", "")
        importer.apply(self.vault, [("Alpha_1", "preenchida")])
        self.assertEqual(self.vault.find("Alpha_1")["password"], "preenchida")

    def test_repeated_in_file(self):
        report = importer.apply(self.vault, [("Alpha_1", "a"), ("alpha_1", "b")])
        self.assertEqual((report.added, report.duplicated), (1, 1))

    def test_limits(self):
        with self.assertRaises(ValidationError):
            importer.parse_accounts("a\n" * 10_001)
        with self.assertRaises(ValidationError):
            importer.parse_bytes(b"\xff\xfe\x00")

    def test_bom_and_crlf(self):
        parsed = importer.parse_bytes("\ufeffabc_1:x\r\ndef_2:y\r\n".encode("utf-8"))
        self.assertEqual(len(parsed.entries), 2)


class SessionTests(Base):
    def test_capture_restore_isolated_per_account(self):
        root = self.dir / "sober"
        cookie = root / "data" / "sober" / "cookies"
        cookie.parent.mkdir(parents=True)
        store = SessionStore(self.vault, self.dir / "sess", root, ("data/sober/cookies",))
        _, one = self.vault.add("Alpha_1", "")
        _, two = self.vault.add("Beta_2", "")
        cookie.write_bytes(b"cookie-um")
        store.capture(one["id"])
        cookie.write_bytes(b"cookie-dois")
        store.capture(two["id"])
        store.restore(one["id"])
        self.assertEqual(cookie.read_bytes(), b"cookie-um")
        blobs = list((self.dir / "sess" / one["id"]).glob("*.bin"))
        self.assertNotIn(b"cookie-um", blobs[0].read_bytes())

    def test_symlink_and_bad_label(self):
        root = self.dir / "sober"
        root.mkdir()
        (root / "data").symlink_to(self.dir)
        store = SessionStore(self.vault, self.dir / "sess", root, ("data/sober/cookies",))
        with self.assertRaises(ManagerError):
            store.live_exists()
        with self.assertRaises(ManagerError):
            store.capture("../escape")

    def test_path_traversal_config(self):
        with self.assertRaises(ManagerError):
            SessionStore(self.vault, self.dir, self.dir, ("../x",))


class LauncherTests(Base):
    def test_uri_and_command(self):
        uri = game_uri("12345", "123e4567-e89b-12d3-a456-426614174000")
        self.assertIn("placeId=12345", uri)
        with self.assertRaises(ValidationError):
            game_uri("12a")
        with self.assertRaises(ValidationError):
            game_uri("1", "nao-e-um-uuid")
        cmd = build_command("flatpak run org.vinegarhq.Sober {uri}", uri, {"A": "b"}, Path("/p"))
        self.assertEqual(cmd[:2], ["flatpak", "run"])
        self.assertIn("--env=A=b", cmd)
        self.assertEqual(cmd[-1], uri)

    def test_blocked_commands(self):
        self.assertEqual(command_problem("bash -c {uri}"), "blocked")
        self.assertEqual(command_problem("python3 x.py {uri}"), "blocked")
        self.assertEqual(command_problem("mocktail"), "invalid")
        self.assertIsNone(command_problem("mocktail {uri}"))

    def test_delete_profile_and_active(self):
        launcher = Launcher(self.vault, self.dir / "perfis", self.dir / "sess", self.dir / "estado.json", self.dir / "sober")
        _, item = self.vault.add("Alpha_1", "")
        (self.dir / "perfis" / item["id"]).mkdir(parents=True)
        launcher.set_active(item["id"])
        self.assertEqual(launcher.active(), item["id"])
        self.assertTrue(launcher.delete_profile(item["id"]))
        self.assertIsNone(launcher.active())
        with self.assertRaises(ManagerError):
            launcher.profile_path("../..")


class SettingsTests(unittest.TestCase):
    def test_tampered_custom_command_discarded(self):
        data = sanitize({"client": "Personalizado", "launch_command": "bash -c {uri}", "allow_custom": True})
        self.assertEqual(data["client"], "Sober (Flatpak)")

    def test_preset_command_never_from_file(self):
        data = sanitize({"client": "Sober (Flatpak)", "launch_command": "rm -rf ~ {uri}"})
        self.assertEqual(data["launch_command"], "flatpak run org.vinegarhq.Sober {uri}")

    def test_garbage(self):
        self.assertEqual(sanitize("x")["theme"], "system")
        self.assertEqual(sanitize({"max_batch": 9999, "fails": -1})["max_batch"], 8)

    def test_lock_backoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(Path(tmp) / "c.json")
            settings.register_failure()
            settings.register_failure()
            self.assertEqual(settings.wait_seconds(), 0)
            self.assertGreater(settings.register_failure(), 0)
            settings.register_success()
            self.assertEqual(settings.wait_seconds(), 0)


class MigrationTests(unittest.TestCase):
    def test_legacy_accounts_keep_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy = tmp / "contas.json"
            legacy.write_text(json.dumps({
                "settings": {"theme": "dark"},
                "accounts": [
                    {"id": "0123456789ab", "alias": "Conta Antiga", "group": "g"},
                    {"id": "../../etc", "alias": "ruim"},
                ],
            }))
            vault, migrated = storage.create_vault(tmp / "cofre.json", "senha-mestra-1", legacy)
            self.assertEqual(migrated, 1)
            self.assertEqual(vault.get("0123456789ab")["username"], "Conta Antiga")
            self.assertFalse(legacy.exists())
            self.assertTrue((tmp / "contas.json.migrado").exists())

    def test_wipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "perfis" / "a").mkdir(parents=True)
            (tmp / "cofre.json").write_text("{}")
            (tmp / "outro.txt").write_text("fica")
            storage.wipe_all(tmp)
            self.assertFalse((tmp / "perfis").exists())
            self.assertFalse((tmp / "cofre.json").exists())
            self.assertTrue((tmp / "outro.txt").exists())


class TranslationTests(unittest.TestCase):
    def test_same_keys_everywhere(self):
        reference = set(LANGS["pt"])
        for code, table in LANGS.items():
            self.assertEqual(set(table), reference, code)

    def test_same_placeholders(self):
        import re
        pattern = re.compile(r"\{(\w+)\}")
        for key, text in LANGS["pt"].items():
            for code, table in LANGS.items():
                self.assertEqual(set(pattern.findall(table[key])), set(pattern.findall(text)), (code, key))

    def test_errors_translate(self):
        self.assertIn("3", str(ValidationError("err_username")))


if __name__ == "__main__":
    unittest.main()
