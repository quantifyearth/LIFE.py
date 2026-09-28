"""Export bounded LIFE data to a standard GeoTIFF."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from affine import Affine

from ._access import Source, _open
from ._catalogue import DEFAULT_CATALOGUE
from ._grid import BBox


def download(layer: str, output: str | os.PathLike[str], *, bounds: Sequence[float],
             source: Source | None = None, version: str | None = None, taxon: str | None = "all",
             level: int = 1, overwrite: bool = False,
             catalogue: str | os.PathLike[str] = DEFAULT_CATALOGUE,
             storage_options: dict[str, Any] | None = None) -> Path:
    """Save a bounded layer as a GeoTIFF and return its path.

    Requires ``life-metric[geo]``. Bounds are west, south, east, north in
    EPSG:4326. The file retains the layer's float32 or float64 dtype, transform,
    units, band descriptions, version, citation, and terms of use. Scores use
    NaN nodata; zero area remains valid. ``taxon=None`` includes every score
    band. Files use lossless DEFLATE compression.

    The output must end in .tif or .tiff. Existing files are refused unless
    ``overwrite=True``. Reads are limited to 16 million values; split larger
    regions. Source and version selection follow :func:`life_metric.metadata`.
    """
    import rasterio

    target = Path(output)
    if target.suffix.lower() not in (".tif", ".tiff"):
        raise ValueError("GeoTIFF output must end in .tif or .tiff")
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} exists; pass overwrite=True to replace it")
    if len(bounds) != 4:
        raise ValueError("bounds must contain west, south, east, north")
    store = _open(source, version, catalogue, storage_options)
    selected = store.get(layer)
    win = selected.grid(level).window(BBox(*bounds))
    count = len(selected.bands) if taxon is None and selected.kind == "score" else 1
    if win.height * win.width * count > 16_000_000:
        raise ValueError("the region is too large for one download; select a smaller bounding box")
    raster = selected.read(taxon, window=win, level=level)
    data = raster.data if raster.is_stack else raster.data[np.newaxis, ...]
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.",
                                         suffix=".tif", delete=False) as temp:
            temporary = Path(temp.name)
        with rasterio.open(temporary, "w", driver="GTiff", width=win.width, height=win.height,
                           count=data.shape[0], dtype=str(data.dtype), crs="EPSG:4326",
                           transform=Affine.from_gdal(*raster.grid.transform),
                           nodata=np.nan if selected.kind == "score" else None,
                           compress="DEFLATE", predictor=3, tiled=True,
                           blockxsize=256, blockysize=256, BIGTIFF="IF_SAFER") as destination:
            destination.write(data)
            destination.update_tags(version=store.version, source=store.source, layer=layer,
                                    resolution_factor=level, units=selected.units,
                                    description=selected.description, citation=store.info.citation or "",
                                    terms_of_use=store.info.terms_of_use or "")
            for index, name in enumerate(raster.bands, start=1):
                destination.set_band_description(index, name)
                destination.set_band_unit(index, selected.units)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target
