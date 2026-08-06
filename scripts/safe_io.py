import pathlib


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]


class UnsafePathError(ValueError):
    pass


PROTECTED_PARTS = (
    (".codex", "skills"),
    (".agents", "skills"),
    ("codex", "skills"),
    ("agents", "skills"),
    (".codex", "plugins"),
    (".agents", "plugins"),
    ("codex", "plugins"),
    ("agents", "plugins"),
)


def resolve_path(path):
    return pathlib.Path(path).expanduser().resolve()


def _broad_output_roots():
    home = pathlib.Path.home().resolve()
    candidates = {pathlib.Path("/").resolve(), home, home / "Documents", home / "Desktop", home / "Downloads"}
    return {candidate.resolve() for candidate in candidates if candidate.exists()}


def _has_parts(path, parts):
    tokens = path.parts
    width = len(parts)
    return any(tuple(tokens[index : index + width]) == parts for index in range(len(tokens) - width + 1))


def _is_within(path, root):
    return path == root or root in path.parents


def _assert_not_protected(path, label):
    resolved = resolve_path(path)
    if _is_within(resolved, SKILL_ROOT) or any(_has_parts(resolved, parts) for parts in PROTECTED_PARTS):
        raise UnsafePathError(f"{label} must not be inside a skill or plugin directory: {resolved}")
    return resolved


def _assert_not_broad_root(path, label):
    resolved = resolve_path(path)
    if resolved in _broad_output_roots():
        raise UnsafePathError(f"{label} must be a project or temporary subdirectory, not a broad root: {resolved}")
    return resolved


def assert_existing_file(path, label="input"):
    resolved = resolve_path(path)
    if not resolved.exists():
        raise UnsafePathError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise UnsafePathError(f"{label} must be a file: {resolved}")
    return resolved


def assert_safe_output_path(path, *, overwrite=False, allowed_suffixes=None, source_paths=()):
    resolved = _assert_not_protected(path, "output path")
    _assert_not_broad_root(resolved.parent, "output parent")
    if allowed_suffixes and resolved.suffix.lower() not in {suffix.lower() for suffix in allowed_suffixes}:
        raise UnsafePathError(f"output path must end with one of {sorted(allowed_suffixes)}: {resolved}")

    for source_path in source_paths:
        if resolved == resolve_path(source_path):
            raise UnsafePathError(f"output path must not be the source file: {resolved}")

    if resolved.exists() and not overwrite:
        raise UnsafePathError(f"output already exists; rerun with --overwrite only after review: {resolved}")

    return resolved


def assert_safe_output_dir(path, *, overwrite=False):
    resolved = _assert_not_protected(path, "output directory")
    _assert_not_broad_root(resolved, "output directory")
    if resolved.exists():
        if not resolved.is_dir():
            raise UnsafePathError(f"output directory path exists but is not a directory: {resolved}")
        if any(resolved.iterdir()) and not overwrite:
            raise UnsafePathError(
                f"output directory is not empty; rerun with --overwrite only after review: {resolved}"
            )
    else:
        _assert_not_protected(resolved.parent, "output parent")
    return resolved


def ensure_parent(path):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
