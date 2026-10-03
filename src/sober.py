import json
import shutil
import subprocess
import time
from pathlib import Path

from .errors import ManagerError, SoberError
from .fsutil import write_private
from .logger import log
from .validation import validate_username

SPAWN_GRACE_SECONDS = 1.5
QUERY_TIMEOUT_SECONDS = 15


class SoberLauncher:
    def __init__(self, sessions, state_file, app_id):
        self._sessions = sessions
        self._state_file = Path(state_file)
        self._app_id = app_id

    def active(self):
        try:
            value = json.loads(self._state_file.read_text(encoding="utf-8")).get("active")
        except (OSError, ValueError, AttributeError):
            return None
        if not isinstance(value, str):
            return None
        try:
            return validate_username(value)
        except ManagerError:
            return None

    def set_active(self, profile):
        payload = json.dumps({"active": profile}).encode("utf-8")
        write_private(self._state_file, payload)

    def clear_active(self):
        try:
            self._state_file.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _flatpak():
        path = shutil.which("flatpak")
        if path is None:
            raise SoberError("flatpak não encontrado no sistema")
        return path

    def _query(self, flatpak, *args):
        try:
            return subprocess.run(
                [flatpak, *args],
                capture_output=True,
                text=True,
                timeout=QUERY_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise SoberError(f"falha ao consultar o flatpak: {exc}") from exc

    def _ensure_ready(self, flatpak):
        if self._query(flatpak, "info", self._app_id).returncode != 0:
            raise SoberError("o Sober não está instalado via flatpak")
        running = self._query(flatpak, "ps", "--columns=application")
        if self._app_id in running.stdout.split():
            raise SoberError("o Sober já está em execução; feche-o antes de trocar de perfil")

    def save_session(self, profile):
        saved = self._sessions.capture(profile)
        if saved:
            self.set_active(profile)
            log.success(f"CONTA [{profile}] SESSÃO SALVA")
        else:
            log.warn("Nenhuma sessão do Sober encontrada para salvar")
        return saved

    def launch(self, profile):
        profile = validate_username(profile)
        flatpak = self._flatpak()
        log.info(f"Iniciando Sober com o perfil: {profile}")
        self._ensure_ready(flatpak)

        previous = self.active()
        if previous:
            if self._sessions.capture(previous):
                log.info(f"Sessão atual guardada no perfil: {previous}")
        elif self._sessions.live_exists():
            self._sessions.backup_live()
            log.info("Sessão anterior sem perfil guardada como backup criptografado")

        if self._sessions.restore(profile):
            log.info(f"Sessão restaurada para o perfil: {profile}")
        else:
            log.warn(f"Perfil {profile} ainda não tem sessão salva; faça login no Sober")
        self.set_active(profile)

        try:
            process = subprocess.Popen(
                [flatpak, "run", self._app_id],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as exc:
            raise SoberError(f"não foi possível iniciar o Sober: {exc}") from exc

        time.sleep(SPAWN_GRACE_SECONDS)
        code = process.poll()
        if code not in (None, 0):
            raise SoberError(f"o Sober encerrou logo após iniciar (código {code})")
        log.success(f"CONTA [{profile}] INICIADA")
