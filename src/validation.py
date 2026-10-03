import os
import re
import shlex

from .errors import ValidationError

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,20}", re.ASCII)
ID_RE = re.compile(r"[0-9a-f]{12}", re.ASCII)
PLACE_RE = re.compile(r"[0-9]{1,19}", re.ASCII)
JOB_RE = re.compile(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", re.ASCII)
FLATPAK_ID_RE = re.compile(r"[A-Za-z0-9_.-]{3,200}", re.ASCII)
CONTROL_RE = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029\u200e\u200f\u202a-\u202e\u2066-\u2069]")

MAX_PASSWORD_LENGTH = 200
MIN_MASTER_LENGTH = 8
MAX_COMMAND_LENGTH = 500

BLOCKED_BINARIES = {
    "sh", "bash", "dash", "zsh", "fish", "csh", "tcsh", "ksh", "env", "sudo", "su", "doas",
    "pkexec", "perl", "ruby", "node", "php", "lua", "nc", "ncat", "socat", "curl", "wget",
    "xterm", "busybox",
}


def clean_text(value, maxlen=60):
    if not isinstance(value, str):
        return ""
    return CONTROL_RE.sub("", value).strip()[:maxlen]


def validate_username(value):
    name = value.strip() if isinstance(value, str) else ""
    if not USERNAME_RE.fullmatch(name):
        raise ValidationError("err_username")
    return name


def validate_password(value):
    if not isinstance(value, str):
        raise ValidationError("err_password_type")
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValidationError("err_password_long")
    if CONTROL_RE.search(value):
        raise ValidationError("err_password_control")
    return value


def validate_master(value):
    if not isinstance(value, str) or len(value) < MIN_MASTER_LENGTH:
        raise ValidationError("err_master_short", n=MIN_MASTER_LENGTH)
    return value


def validate_game(place, job=""):
    if not PLACE_RE.fullmatch(place):
        raise ValidationError("warn_game")
    if job and not JOB_RE.fullmatch(job):
        raise ValidationError("warn_job")
    return place, job


def command_problem(cmd):
    if (
        not isinstance(cmd, str)
        or len(cmd) > MAX_COMMAND_LENGTH
        or CONTROL_RE.search(cmd)
        or "{uri}" not in cmd
    ):
        return "invalid"
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return "invalid"
    if not parts:
        return "invalid"
    name = os.path.basename(parts[0])
    if name in BLOCKED_BINARIES or re.fullmatch(r"python[\d.]*", name):
        return "blocked"
    return None
