import os
import sys

from . import cli, config
from .errors import ManagerError
from .fsutil import ensure_private_dir
from .idiomas import resolve_language, set_language, tr, translate
from .logger import log
from .settings import Settings
from .storage import read_legacy


def load_settings():
    settings = Settings()
    if not settings.loaded and settings.warning is None:
        legacy = read_legacy(config.LEGACY_FILE)
        if legacy is not None:
            settings.replace(legacy[0])
            settings.save()
    return settings


def run_gui(settings, qt_args):
    try:
        from . import gui
    except ModuleNotFoundError as exc:
        if (exc.name or "").split(".")[0] != "PySide6":
            raise
        log.error(tr("err_deps"))
        return 1
    return gui.run(settings, qt_args)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if os.geteuid() == 0:
        print(translate("pt", "root_refuse"), file=sys.stderr)
        print(translate("en", "root_refuse"), file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        ensure_private_dir(config.CONFIG_DIR)
        settings = load_settings()
    except (ManagerError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    set_language(resolve_language(settings["language"]))
    log.configure(config.LOG_FILE)
    if settings.warning:
        log.warn(tr(settings.warning))
    parser = cli.build_parser()
    args, extra = parser.parse_known_args(argv)
    if args.command == "version":
        print(config.read_version())
        return 0
    if args.command is not None and extra:
        parser.error("unrecognized arguments: " + " ".join(extra))
    try:
        if args.command is None:
            return run_gui(settings, extra)
        cli.run(args, settings)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        log.info(tr("log_interrupted"))
        return 130
    except ManagerError as exc:
        log.error(str(exc))
        return 1
    except OSError as exc:
        log.error(exc.strerror or str(exc))
        return 1
    return 0
