import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from . import config
from .errors import ClientError, ManagerError
from .fsutil import ensure_private_dir, write_private
from .idiomas import tr
from .logger import log
from .sessions import SessionStore
from .settings import CLIENT_CUSTOM, SWAP_CLIENT
from .validation import FLATPAK_ID_RE, ID_RE, command_problem, validate_game

QUERY_TIMEOUT_SECONDS = 15
CLIENT_LOG_LIMIT = 1_000_000


@dataclass
class StartResult:
    command: list
    log_path: Path
    process: subprocess.Popen


def game_uri(place, job=""):
    validate_game(place, job)
    query = {"placeId": place}
    if job:
        query["gameInstanceId"] = job
    return "roblox://experiences/start?" + urlencode(query)


def build_command(template, uri, profile_env=None, profile=None):
    parts = shlex.split(template)
    if uri is None:
        parts = [part for part in parts if "{uri}" not in part]
    else:
        parts = [part.replace("{uri}", uri) for part in parts]
    if profile_env and parts[:2] == ["flatpak", "run"]:
        extra = [f"--env={key}={value}" for key, value in profile_env.items()]
        extra.append(f"--filesystem={profile}")
        parts = parts[:2] + extra + parts[2:]
    return parts


def client_missing(template):
    parts = shlex.split(template)
    if not parts:
        return "?"
    if parts[0] == "flatpak":
        if not shutil.which("flatpak"):
            return "flatpak"
        app_id = next((part for part in parts[2:] if not part.startswith("-")), "")
        if not FLATPAK_ID_RE.fullmatch(app_id):
            return app_id or "?"
        try:
            found = subprocess.run(
                ["flatpak", "info", app_id], capture_output=True, timeout=QUERY_TIMEOUT_SECONDS
            ).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            found = False
        return None if found else app_id
    return None if shutil.which(parts[0]) else parts[0]


def profile_env(profile):
    env = {
        "XDG_CONFIG_HOME": str(profile / "config"),
        "XDG_DATA_HOME": str(profile / "data"),
        "XDG_CACHE_HOME": str(profile / "cache"),
        "XDG_STATE_HOME": str(profile / "state"),
    }
    for value in env.values():
        ensure_private_dir(Path(value))
    return env


class Launcher:
    def __init__(self, vault, profiles_dir, sessions_dir, state_file, sober_root=None):
        self.vault = vault
        self.profiles_dir = Path(profiles_dir)
        self.state_file = Path(state_file)
        self.sessions = SessionStore(
            vault, sessions_dir, sober_root or config.SOBER_ROOT, config.SESSION_FILES
        )

    def profile_path(self, account_id):
        if not ID_RE.fullmatch(account_id):
            raise ManagerError("err_account_id")
        return self.profiles_dir / account_id

    def active(self):
        try:
            value = json.loads(self.state_file.read_text(encoding="utf-8")).get("active")
        except (OSError, ValueError, AttributeError):
            return None
        if isinstance(value, str) and ID_RE.fullmatch(value) and self.vault.get(value):
            return value
        return None

    def set_active(self, account_id):
        write_private(self.state_file, json.dumps({"active": account_id}).encode("utf-8"))

    def clear_active(self):
        try:
            self.state_file.unlink()
        except FileNotFoundError:
            pass

    def delete_profile(self, account_id):
        removed = False
        path = self.profile_path(account_id)
        if path.exists() and not path.is_symlink():
            if path.resolve().parent != self.profiles_dir.resolve():
                raise ManagerError("err_profile_outside")
            shutil.rmtree(path)
            removed = True
        if self.sessions.has_snapshot(account_id):
            self.sessions.delete(account_id)
            removed = True
        if self.active() == account_id:
            self.clear_active()
        return removed

    @staticmethod
    def _flatpak():
        path = shutil.which("flatpak")
        if path is None:
            raise ClientError("err_flatpak_missing")
        return path

    @staticmethod
    def _query(flatpak, *args):
        try:
            return subprocess.run(
                [flatpak, *args],
                capture_output=True,
                text=True,
                timeout=QUERY_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ClientError("err_flatpak_query", why=str(exc)) from exc

    def _ensure_ready(self, flatpak, app_id):
        if self._query(flatpak, "info", app_id).returncode != 0:
            raise ClientError("err_sober_missing")
        running = self._query(flatpak, "ps", "--columns=application")
        if app_id in running.stdout.split():
            raise ClientError("err_sober_running")

    def _name(self, account_id):
        item = self.vault.get(account_id)
        return item["username"] if item else account_id

    def _swap_to(self, target):
        previous = self.active()
        if previous:
            if self.sessions.capture(previous):
                log.info(tr("log_session_prev", name=self._name(previous)))
        elif self.sessions.live_exists():
            self.sessions.backup_live()
            log.info(tr("log_session_backup"))
        if self.sessions.restore(target):
            log.info(tr("log_session_restored", name=self._name(target)))
        else:
            log.warn(tr("log_session_missing", name=self._name(target)))
        self.set_active(target)

    def save_session(self, account_id):
        saved = self.sessions.capture(account_id)
        if saved:
            self.set_active(account_id)
            log.success(tr("log_session_saved", name=self._name(account_id)))
        else:
            log.warn(tr("log_session_none"))
        return saved

    def _spawn(self, command, env, log_path):
        try:
            if log_path.stat().st_size > CLIENT_LOG_LIMIT:
                log_path.unlink()
        except OSError:
            pass
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            return subprocess.Popen(
                command,
                env=env,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=fd,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
        except OSError as exc:
            raise ClientError("err_client_start", why=exc.strerror or str(exc)) from exc
        finally:
            os.close(fd)

    def start(self, account_id, settings, uri):
        if settings["client"] == CLIENT_CUSTOM and (
            not settings["allow_custom"] or command_problem(settings["launch_command"])
        ):
            raise ClientError("err_custom_denied")
        profile = self.profile_path(account_id)
        ensure_private_dir(self.profiles_dir)
        ensure_private_dir(profile)
        env = os.environ.copy()
        if settings["isolate_profiles"]:
            penv = profile_env(profile)
            env.update(penv)
            command = build_command(settings["launch_command"], uri, penv, profile)
        else:
            if settings["client"] != SWAP_CLIENT:
                raise ClientError("err_swap_client")
            flatpak = self._flatpak()
            self._ensure_ready(flatpak, config.SOBER_APP_ID)
            self._swap_to(account_id)
            command = build_command(settings["launch_command"], uri)
        log_path = profile / "cliente.log"
        process = self._spawn(command, env, log_path)
        return StartResult(command, log_path, process)
