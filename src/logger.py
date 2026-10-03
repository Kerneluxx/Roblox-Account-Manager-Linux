import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")
logging.addLevelName(logging.WARNING, "WARN")

CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
COLORS = {
    "INFO": "\033[36m",
    "SUCCESS": "\033[32m",
    "WARN": "\033[33m",
    "ERROR": "\033[31m",
}
RESET = "\033[0m"


class ConsoleFormatter(logging.Formatter):
    def __init__(self, color):
        super().__init__()
        self._color = color

    def format(self, record):
        tag = f"[{record.levelname}]"
        if self._color:
            tag = f"{COLORS.get(record.levelname, '')}{tag}{RESET}"
        text = f"{tag} {record.getMessage()}"
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        return text


class Log:
    def __init__(self):
        self._logger = logging.getLogger("gerenciador_contas")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._listeners = []
        self._configured = False

    def configure(self, log_file=None):
        if self._configured:
            return
        color = sys.stderr.isatty() and "NO_COLOR" not in os.environ
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(ConsoleFormatter(color))
        self._logger.addHandler(console)
        if log_file is not None:
            try:
                handler = RotatingFileHandler(
                    log_file, maxBytes=512_000, backupCount=2, encoding="utf-8"
                )
            except OSError:
                handler = None
            if handler is not None:
                handler.setFormatter(
                    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
                )
                self._logger.addHandler(handler)
                try:
                    os.chmod(log_file, 0o600)
                except OSError:
                    pass
        self._configured = True

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _emit(self, level, message, exc_info=None):
        text = CONTROL_RE.sub(" ", str(message))
        self._logger.log(level, text, exc_info=exc_info)
        name = logging.getLevelName(level)
        for callback in list(self._listeners):
            try:
                callback(name, text)
            except Exception:
                pass

    def info(self, message):
        self._emit(logging.INFO, message)

    def success(self, message):
        self._emit(SUCCESS, message)

    def warn(self, message):
        self._emit(logging.WARNING, message)

    def error(self, message, exc_info=None):
        self._emit(logging.ERROR, message, exc_info)


log = Log()
