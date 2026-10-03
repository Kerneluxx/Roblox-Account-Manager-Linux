from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config, importer
from .errors import ValidationError, VaultError, WrongPassword
from .fsutil import ensure_private_dir, write_private
from .logger import log
from .sessions import SessionStore
from .sober import SoberLauncher
from .vault import Vault


@dataclass(frozen=True)
class AccountRow:
    name: str
    has_password: bool
    has_session: bool
    active: bool


def unlock_vault(password):
    return Vault.open(config.VAULT_FILE, password)


def create_vault(password):
    vault = Vault.create(config.VAULT_FILE, password)
    vault.save()
    return vault


class Service:
    def __init__(self, vault, sober_root=None, sessions_dir=None, state_file=None):
        self.vault = vault
        self.sessions = SessionStore(
            vault,
            sessions_dir or config.SESSIONS_DIR,
            sober_root or config.SOBER_ROOT,
            config.SESSION_FILES,
        )
        self.launcher = SoberLauncher(
            self.sessions, state_file or config.STATE_FILE, config.SOBER_APP_ID
        )

    def verify_master(self, password):
        try:
            Vault.open(self.vault.path, password)
        except WrongPassword:
            log.error("Senha mestra incorreta na confirmação")
            raise VaultError("senha mestra incorreta") from None

    def rows(self):
        active = self.launcher.active()
        return [
            AccountRow(
                name=name,
                has_password=bool(self.vault.get_password(name)),
                has_session=self.sessions.has_snapshot(name),
                active=name == active,
            )
            for name in self.vault.names()
        ]

    def add(self, name, password):
        if self.vault.add(name, password) == "exists":
            raise VaultError("essa conta já existe")
        self.vault.save()
        log.success(f"CONTA [{name.strip()}] ADICIONADA")

    def set_password(self, name, password):
        self.vault.set_password(name, password)
        self.vault.save()
        log.success(f"CONTA [{name}] SENHA ALTERADA")

    def remove(self, name):
        removed = self.vault.remove(name)
        self.sessions.delete(removed)
        if self.launcher.active() == removed:
            self.launcher.clear_active()
        self.vault.save()
        log.success(f"CONTA [{removed}] REMOVIDA")

    def reveal(self, name, master):
        self.verify_master(master)
        log.info(f"CONTA [{name}] SENHA EXIBIDA")
        return self.vault.get_password(name)

    def launch(self, name):
        self.launcher.launch(name)

    def save_session(self, name=None):
        target = name or self.launcher.active()
        if target is None or self.vault.find(target) is None:
            raise VaultError("nenhum perfil ativo; selecione uma conta")
        self.launcher.save_session(target)

    def import_file(self, path, overwrite):
        path = Path(path).expanduser()
        log.info(f"Lendo arquivo de importação: {path}")
        parsed = importer.load_file(path)
        for number, reason in parsed.invalid:
            log.warn(f"Linha {number} ignorada: {reason}")
        if not parsed.entries:
            log.warn("Nenhuma conta válida encontrada no arquivo")
            return importer.ImportReport(), parsed
        report = importer.apply(self.vault, parsed.entries, overwrite=overwrite)
        self.vault.save()
        log.success(
            f"IMPORTAÇÃO CONCLUÍDA: {report.added} nova(s), {report.updated} atualizada(s), "
            f"{report.skipped} ignorada(s), {report.duplicated} repetida(s) no arquivo, "
            f"{len(parsed.invalid)} linha(s) inválida(s)"
        )
        return report, parsed

    @staticmethod
    def default_export_path():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return config.EXPORTS_DIR / f"contas-{stamp}.txt"

    def export_file(self, path, master):
        if not self.vault.names():
            raise VaultError("nenhuma conta para exportar")
        self.verify_master(master)
        target = Path(path).expanduser()
        if target.is_dir():
            raise ValidationError("o destino é um diretório")
        if target.parent == config.EXPORTS_DIR:
            ensure_private_dir(config.EXPORTS_DIR)
        try:
            write_private(target, importer.export_text(self.vault).encode("utf-8"))
        except OSError as exc:
            raise ValidationError(f"não foi possível gravar o arquivo: {exc}") from exc
        log.success(f"EXPORTAÇÃO CONCLUÍDA: {len(self.vault.names())} conta(s) em {target}")
        log.warn("O arquivo exportado contém senhas em texto puro; apague-o após o uso")
        return target

    def change_master(self, current, new):
        self.verify_master(current)
        self.vault.change_password(new)
        self.vault.save()
        log.success("SENHA MESTRA ALTERADA")
