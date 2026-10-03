import shutil
import subprocess

COMMANDS = (
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
)


def available():
    return any(shutil.which(command[0]) for command in COMMANDS)


def copy_text(text):
    for command in COMMANDS:
        path = shutil.which(command[0])
        if path is None:
            continue
        try:
            subprocess.run(
                [path, *command[1:]],
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        return True
    return False
