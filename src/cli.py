import argparse
import getpass
import time
from datetime import datetime
from pathlib import Path

from . import config, importer, storage
from .errors import ClientError, ValidationError, VaultError, WrongPassword
from .fsutil import ensure_private_dir, write_private
from .idiomas import tr
from .launcher import Launcher, client_missing, game_uri
from .logger import log
from .vault import Vault

YES = {"s", "sim", "y", "yes", "o", "oui", "j", "ja"}
EXIT_GRACE_SECONDS = 1.5
STAMP_FORMAT = "%d/%m %H:%M"


def read_line(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        raise KeyboardInterrupt from None


def read_secret(prompt):
    try:
        return getpass.getpass(prompt)
    except EOFError:
        raise KeyboardInterrupt from None


def confirm(prompt):
    return read_line(prompt).lower() in YES


def create_vault():
    while True:
        first = read_secret(tr("cli_prompt_new"))
        if first != read_secret(tr("cli_prompt_repeat")):
            log.error(tr("pw_mismatch"))
            continue
        try:
            vault, migrated = storage.create_vault(config.VAULT_FILE, first, config.LEGACY_FILE)
        except ValidationError as exc:
            log.error(str(exc))
            continue
        log.success(tr("log_vault_created"))
        if migrated:
            log.info(tr("log_migrated", n=migrated))
        return vault


def unlock(settings):
    if not config.VAULT_FILE.exists():
        return create_vault()
    for _ in range(config.MAX_UNLOCK_ATTEMPTS):
        wait = settings.wait_seconds()
        if wait:
            raise VaultError("lock_wait", n=wait)
        try:
            vault = Vault.open(config.VAULT_FILE, read_secret(tr("cli_prompt_master")))
        except WrongPassword:
            settings.register_failure()
            log.error(tr("log_unlock_fail", n=settings["fails"]))
            continue
        settings.register_success()
        log.success(tr("log_vault_unlocked", n=len(vault)))
        return vault
    raise VaultError("err_attempts")


class Commands:
    def __init__(self, vault, settings):
        self.vault = vault
        self.settings = settings
        self.launcher = Launcher(
            vault, config.PROFILES_DIR, config.SESSIONS_DIR, config.STATE_FILE
        )

    def resolve(self, token):
        found = self.vault.find(token)
        if found is not None:
            return found
        accounts = self.vault.all()
        if token.strip().isdigit() and token.strip().isascii():
            index = int(token)
            if 1 <= index <= len(accounts):
                return accounts[index - 1]
        raise VaultError("err_not_found")

    def reauthenticate(self):
        if not self.vault.verify(read_secret(tr("cli_prompt_confirm"))):
            raise VaultError("err_wrong_master")

    def list_accounts(self):
        accounts = self.vault.all()
        if not accounts:
            log.info(tr("err_no_accounts"))
            return
        active = self.launcher.active()
        header = ("#", tr("col_user"), tr("col_password"), tr("col_group"), tr("col_last"))
        rows = [header]
        for index, item in enumerate(accounts, start=1):
            last = item["last_launch"] or "-"
            if item["id"] == active:
                last += " *"
            rows.append(
                (str(index), item["username"], "****" if item["password"] else "-",
                 item["group"] or "-", last)
            )
        widths = [max(len(row[column]) for row in rows) for column in range(len(header))]
        for row in rows:
            print("  ".join(cell.ljust(widths[column]) for column, cell in enumerate(row)).rstrip())
        log.info(tr("log_count", n=len(accounts)))

    def add_account(self, username):
        password = read_secret(tr("cli_prompt_pass"))
        outcome, item = self.vault.add(username, password)
        if outcome == "exists":
            raise VaultError("err_exists", name=item["username"])
        self.vault.save()
        log.success(tr("log_added", name=item["username"]))

    def remove_account(self, token, assume_yes=False):
        item = self.resolve(token)
        if not assume_yes and not confirm(tr("cli_confirm_remove", name=item["username"])):
            return
        self.launcher.delete_profile(item["id"])
        self.vault.remove(item["id"])
        self.vault.save()
        log.success(tr("log_removed", name=item["username"]))

    def import_file(self, path, overwrite):
        path = Path(path).expanduser()
        log.info(tr("log_import_read", path=path))
        parsed = importer.load_file(path)
        for number, key in parsed.invalid:
            log.warn(tr("log_import_line", n=number, why=tr(key)))
        if not parsed.entries:
            log.warn(tr("log_import_none"))
            return
        clash = importer.conflicts(self.vault, parsed.entries)
        if clash and not overwrite and confirm(tr("cli_confirm_overwrite", n=clash)):
            overwrite = True
        report = importer.apply(self.vault, parsed.entries, overwrite)
        self.vault.save()
        log.success(
            tr(
                "log_import_done",
                added=report.added,
                updated=report.updated,
                skipped=report.skipped,
                duplicated=report.duplicated,
                invalid=len(parsed.invalid),
            )
        )

    def export_file(self, path, force):
        if not len(self.vault):
            raise VaultError("err_no_accounts")
        self.reauthenticate()
        if path:
            target = Path(path).expanduser()
        else:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = config.EXPORTS_DIR / f"contas-{stamp}.txt"
        if target.is_dir():
            raise ValidationError("err_write", why=str(target))
        if target.exists() and not force and not confirm(tr("cli_confirm_replace", path=target)):
            return
        if target.parent == config.EXPORTS_DIR:
            ensure_private_dir(config.EXPORTS_DIR)
        try:
            write_private(target, importer.export_text(self.vault).encode("utf-8"))
        except OSError as exc:
            raise ValidationError("err_write", why=exc.strerror or str(exc)) from exc
        log.success(tr("log_export_done", n=len(self.vault), path=target))
        log.warn(tr("log_export_warn"))

    def launch(self, token, place, job):
        item = self.resolve(token)
        uri = game_uri(place, job) if place else None
        missing = client_missing(self.settings["launch_command"])
        if missing:
            raise ClientError("client_missing", name=missing)
        log.info(tr("log_launch", name=item["username"]))
        result = self.launcher.start(item["id"], self.settings, uri)
        log.info(tr("log_output", path=result.log_path))
        time.sleep(EXIT_GRACE_SECONDS)
        code = result.process.poll()
        if code not in (None, 0):
            raise ClientError(
                "log_client_exit", name=item["username"], code=code, path=result.log_path
            )
        self.vault.touch(item["id"], time.strftime(STAMP_FORMAT))
        self.vault.save()


def build_parser():
    parser = argparse.ArgumentParser(prog="main.py", description=tr("cli_desc"))
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help=tr("cli_list"))
    add = sub.add_parser("add", help=tr("cli_add"))
    add.add_argument("account", help=tr("cli_account"))
    remove = sub.add_parser("remove", help=tr("cli_remove"))
    remove.add_argument("account", help=tr("cli_account"))
    remove.add_argument("-y", "--yes", action="store_true", help=tr("cli_yes"))
    imp = sub.add_parser("import", help=tr("cli_import"))
    imp.add_argument("file", help=tr("cli_file"))
    imp.add_argument("--overwrite", action="store_true", help=tr("cli_overwrite"))
    exp = sub.add_parser("export", help=tr("cli_export"))
    exp.add_argument("file", nargs="?", help=tr("cli_file"))
    exp.add_argument("--force", action="store_true", help=tr("cli_force"))
    launch = sub.add_parser("launch", help=tr("cli_launch"))
    launch.add_argument("account", help=tr("cli_account"))
    launch.add_argument("--place", default="", help=tr("ph_place"))
    launch.add_argument("--job", default="", help=tr("ph_job"))
    sub.add_parser("version", help=tr("cli_version"))
    return parser


def run(args, settings):
    commands = Commands(unlock(settings), settings)
    if args.command == "list":
        commands.list_accounts()
    elif args.command == "add":
        commands.add_account(args.account)
    elif args.command == "remove":
        commands.remove_account(args.account, args.yes)
    elif args.command == "import":
        commands.import_file(args.file, args.overwrite)
    elif args.command == "export":
        commands.export_file(args.file, args.force)
    elif args.command == "launch":
        commands.launch(args.account, args.place, args.job)
