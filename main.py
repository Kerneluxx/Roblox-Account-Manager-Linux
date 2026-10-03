import sys

if sys.version_info < (3, 10):
    sys.exit("[ERROR] Python 3.10+ / Python 3.10 ou superior")

try:
    from src.app import main
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] == "cryptography":
        sys.exit("[ERROR] Missing dependency / Dependência ausente: pip install -r requirements.txt")
    raise

if __name__ == "__main__":
    sys.exit(main())
