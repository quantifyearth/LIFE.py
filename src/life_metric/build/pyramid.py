"""Overview levels (a resolution pyramid) so a viewer can paint the globe fast.

Levels follow the zarr-conventions multiscales layout: the root group's
``multiscales.layout`` lists each level group by name, ``"0"`` for the base
and ``"1"``, ``"2"``, ``"3"``, ``"4"`` for factors 2, 4, 8 and 16, each
derived from the previous with ``transform.scale`` [2, 2] and an absolute
``spatial:transform``. Every level group is a complete dataset with its own
coordinates and every layer.

The base level spans the full 90N..90S globe, so a level pixel is
the mean of the finite pixels of its 2x2 block in the level above, NaN where
all four are missing, and all levels share the origin (-180, 90). Units are
unchanged. These levels are for visualisation: a mean of per-km2 scores is
not the score of the larger area.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path

import numpy as np
import zarr

from .. import dataset as L
from typing import Any

from numpy.typing import NDArray

from .._store import _array_at
from ..dataset import FACTORS, Layer
from .convert import Options, create_level, layout_of, set_layout


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def downsample2(a: NDArray[Any]) -> NDArray[Any]:
    """Halve both axes by averaging finite values, retaining the input dtype."""
    h, w = a.shape
    if h % 2 or w % 2:
        a = np.pad(a, ((0, h % 2), (0, w % 2)), constant_values=np.nan)
        h, w = a.shape
    finite = np.isfinite(a)
    total = np.where(finite, a, 0).reshape(h // 2, 2, w // 2, 2).sum(axis=(1, 3), dtype="float64")
    count = finite.reshape(h // 2, 2, w // 2, 2).sum(axis=(1, 3), dtype="int32")
    out: NDArray[Any] = (total / np.maximum(count, 1)).astype(a.dtype)
    out[count == 0] = np.nan
    return out


def create_pyramid(
    store_path: Path,
    opts: Options,
    which: list[Layer],
    factors: tuple[int, ...] = FACTORS,
    chunk: int = 512,
    overwrite: bool = False,
) -> None:
    """Create the level groups for *factors* and list them in the ``multiscales`` layout."""
    root = zarr.open_group(store_path, mode="r+", use_consolidated=False)
    for f in factors:
        create_level(root, opts, f, which, chunk, overwrite=overwrite)
    existing = [int(e["factor"]) for e in _level_entries(root) if e["factor"] > 1]
    set_layout(root, opts, sorted(set(existing) | set(factors)))


def _level_entries(root: zarr.Group) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in layout_of(root):
        name = str(entry["asset"])
        if name in root:
            factor = root[name].attrs.get("factor")
            out.append({"asset": name, "factor": int(factor) if isinstance(factor, (int, float)) else 2 ** int(name)})
    return out


def build_band(store_path: str, name: str, band: int, factors: tuple[int, ...]) -> tuple[str, int, float]:
    """Compute every level of one band of one layer. Runs in a worker process."""
    t0 = time.monotonic()
    zarr.config.set({"array.write_empty_chunks": False})
    base = zarr.open_array(store_path, path=f"{L.level_name(1)}/{name}", mode="r")
    a = np.asarray(base[band] if base.ndim == 3 else base[:])
    f = 1
    for target in factors:
        while f < target:
            a = downsample2(a)
            f *= 2
        level = zarr.open_array(store_path, path=f"{L.level_name(target)}/{name}", mode="r+")
        if level.ndim == 3:
            level[band] = a
        else:
            level[:] = a
    return name, band, time.monotonic() - t0


def build_pyramid(
    store_path: Path,
    which: list[Layer],
    factors: tuple[int, ...] = FACTORS,
    workers: int = 8,
) -> None:
    """Fill overview arrays by averaging finite cells from the level above."""
    if any(f & (f - 1) or f < 2 for f in factors) or list(factors) != sorted(factors):
        raise ValueError(f"factors must be ascending powers of two, got {factors}")
    tasks = [(layer.name, b) for layer in which for b in range(len(layer.bands))]
    t0 = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(build_band, str(store_path), n, b, tuple(factors)) for n, b in tasks]
        for i, fut in enumerate(as_completed(futures), start=1):
            name, band, secs = fut.result()
            _log(f"  pyramid {i}/{len(tasks)}: {name} band {band} in {secs:.0f}s")
    root = zarr.open_group(store_path, mode="r+", use_consolidated=False)
    for f in factors:
        for layer in which:
            arr = _array_at(root, f"{L.level_name(f)}/{layer.name}")
            arr.attrs["chunks_written"] = arr.nchunks_initialized
            arr.attrs["chunks_total"] = arr.nchunks
    _log(f"pyramid built in {time.monotonic() - t0:.0f}s")
