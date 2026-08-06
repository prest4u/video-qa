import atexit
import pathlib
import sys


def install(skill_dir):
    sys.dont_write_bytecode = True
    root = pathlib.Path(skill_dir).resolve()

    def cleanup():
        for pycache in (root / "scripts" / "__pycache__", root / "tests" / "__pycache__"):
            if not pycache.is_dir():
                continue
            for child in pycache.iterdir():
                if child.is_file() and child.suffix == ".pyc":
                    child.unlink()
            try:
                pycache.rmdir()
            except OSError:
                pass

    atexit.register(cleanup)
