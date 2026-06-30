import inspect
from pathlib import Path

from ._settings import Settings


def find_caller() -> Path:
    package_root = Path(__file__).resolve().parent.parent

    caller_file: Path | None = None
    for frame in inspect.stack():
        # Skip synthetic frames (<string>, <frozen ...>) that aren't real files.
        if frame.filename.startswith("<"):
            continue
        frame_file = Path(frame.filename).resolve()
        if package_root not in frame_file.parents:
            caller_file = frame_file
            break

    if caller_file is None:
        raise ValueError("Could not determine the calling script outside alchemy_kit")

    return caller_file

def find_project_root() -> Path:
    caller_file = find_caller()

    project_root: Path | None = None
    for directory in (caller_file.parent, *caller_file.parents):
        if any((directory / marker).exists() for marker in Settings.project_markers):
            project_root = directory
            break

    if project_root is None:
        raise ValueError(f"Could not find a project root above {caller_file}")

    return project_root
