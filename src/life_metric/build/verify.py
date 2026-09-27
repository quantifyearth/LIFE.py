"""Check the store against the source GeoTIFFs, bit for bit.

Two independent readers are used:

* zarr-python reads the store and numpy compares it to rasterio's view of
  the GeoTIFF, block by block, treating NaN == NaN;
* optionally GDAL's own Zarr driver (via rasterio) reads a few windows, which
  proves the store is usable from QGIS, gdal_translate and friends.
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import zarr
from rasterio.windows import Window

from .. import dataset as L
from .convert import row_blocks
from ..dataset import Layer


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _equal(a: np.ndarray, b: np.ndarray) -> int:
    """Number of differing cells, NaN counted as equal to NaN."""
    if a.shape != b.shape:
        return a.size
    return int(np.count_nonzero(~((a == b) | (np.isnan(a) & np.isnan(b)))))


def verify_block(store_path: str, name: str, tif: str, row0: int, row1: int,
                 row_offset: int = L.ROW_OFFSET) -> tuple[int, int, int]:
    """Compare source rows [row0, row1) with the corresponding store rows."""
    with rasterio.open(tif) as src:
        expect = src.read(window=Window(0, row0, src.width, row1 - row0))
    arr = zarr.open_array(store_path, path=f"{L.level_name(1)}/{name}", mode="r")
    t0, t1 = row0 + row_offset, row1 + row_offset
    got = np.asarray(arr[t0:t1, :] if arr.ndim == 2 else arr[:, t0:t1, :])
    if arr.ndim == 2:
        expect = expect[0]
    return row0, row1, _equal(got, expect)


def polar_rows_are_fill(store_path: str, name: str, row_offset: int = L.ROW_OFFSET) -> bool:
    """The padded first and last rows of the base level must be fill value."""
    if not row_offset:
        return True
    arr = zarr.open_array(store_path, path=f"{L.level_name(1)}/{name}", mode="r")
    fill = np.nan if arr.fill_value is None else float(arr.fill_value)
    edges = [np.asarray(arr[..., :row_offset, :]), np.asarray(arr[..., -row_offset:, :])]
    return all(_equal(e, np.full_like(e, fill)) == 0 for e in edges)


@dataclass
class VerifyResult:
    """Source comparison counts and the optional GDAL cross-check result."""
    name: str
    blocks: int
    mismatched_cells: int
    gdal_ok: bool | None = None

    @property
    def ok(self) -> bool:
        """Whether every cell and requested GDAL check matched."""
        return self.mismatched_cells == 0 and self.gdal_ok is not False


def gdal_crosscheck(store_path: Path, layer: Layer, tif: Path, rows: int = 512,
                    row_offset: int = L.ROW_OFFSET) -> bool:
    """Read three windows of the base level through GDAL's Zarr driver and compare."""
    ds_name = f'ZARR:"{store_path}":/{L.level_name(1)}/{layer.name}'
    ok = True
    with rasterio.open(ds_name) as zds, rasterio.open(tif) as tds:
        if (zds.height, zds.width, zds.count) != (tds.height + 2 * row_offset, tds.width, tds.count):
            _log(f"  gdal: shape mismatch {zds.shape}x{zds.count} vs {tds.shape}x{tds.count} (+padding)")
            return False
        if zds.crs != tds.crs:
            _log(f"  gdal: crs mismatch {zds.crs} vs {tds.crs}")
            ok = False
        if not np.allclose(zds.transform.to_gdal(), L.geotransform(1), atol=1e-9):
            _log(f"  gdal: transform mismatch {zds.transform.to_gdal()} vs {L.geotransform(1)}")
            ok = False
        h = tds.height
        rows = min(rows, h)
        for row0 in sorted({0, max(0, h // 2 - rows // 2), h - rows}):
            twin = Window(0, row0, tds.width, rows)
            zwin = Window(0, row0 + row_offset, tds.width, rows)
            if _equal(zds.read(window=zwin), tds.read(window=twin)):
                _log(f"  gdal: data mismatch in source rows {row0}-{row0 + rows}")
                ok = False
    return ok


def verify_layers(
    store_path: Path,
    raw_dir: Path,
    which: list[Layer],
    workers: int = 8,
    rows: int = 1024,
    gdal: bool = False,
) -> list[VerifyResult]:
    """Compare base-level Zarr arrays with source GeoTIFFs, including polar fill rows."""
    results: list[VerifyResult] = []
    root = zarr.open_group(store_path, mode="r")
    grid_attrs = root.attrs.get("grid")
    offset = grid_attrs.get("row_offset") if isinstance(grid_attrs, dict) else None
    row_offset = int(offset) if isinstance(offset, (int, float)) else L.ROW_OFFSET
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for layer in which:
            tif = raw_dir / layer.source
            with rasterio.open(tif) as src:
                height = src.height
            blocks = row_blocks(height, rows)
            futures = [
                pool.submit(verify_block, str(store_path), layer.name, str(tif), r0, r1, row_offset)
                for r0, r1 in blocks
            ]
            bad = 0
            for fut in as_completed(futures):
                r0, r1, n = fut.result()
                if n:
                    _log(f"  {layer.name}: {n} mismatched cells in rows {r0}-{r1}")
                bad += n
            if not polar_rows_are_fill(str(store_path), layer.name, row_offset):
                _log(f"  {layer.name}: polar fill rows are not fill value")
                bad += 1
            res = VerifyResult(layer.name, len(blocks), bad)
            if gdal:
                res.gdal_ok = gdal_crosscheck(store_path, layer, tif, row_offset=row_offset)
            _log(f"{layer.name}: {'OK' if res.ok else 'FAIL'} ({bad} mismatched cells"
                 + (f", gdal {'ok' if res.gdal_ok else 'FAIL'}" if gdal else "") + ")")
            results.append(res)
    return results
