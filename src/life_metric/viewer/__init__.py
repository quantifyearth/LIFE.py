"""Install the static browser viewer into a store."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

LIB_DIR = "life-metric"


def install_viewer(store_path: Path, lib_dir: Path | None = None) -> list[Path]:
    """Copy ``index.html`` and the ``life-metric`` browser library into the store root.

    The library is the bundled copy unless *lib_dir* points at a built
    ``dist`` directory of the TypeScript package. Returns the paths written.
    """
    out = []
    src = resources.files("life_metric") / "viewer"
    with resources.as_file(src / "index.html") as p:
        dest = store_path / "index.html"
        shutil.copyfile(p, dest)
        out.append(dest)
    target = store_path / LIB_DIR
    target.mkdir(exist_ok=True)
    if lib_dir is not None:
        files = sorted(lib_dir.glob("*.js"))
    else:
        with resources.as_file(src / LIB_DIR) as d:
            files = sorted(Path(d).glob("*.js"))
    for f in files:
        shutil.copyfile(f, target / f.name)
        out.append(target / f.name)
    stale = store_path / "viewer.js"
    if stale.exists():
        stale.unlink()
    return out
