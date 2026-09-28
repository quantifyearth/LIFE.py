"""Read LIFE data into NumPy and xarray objects."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, TypeAlias, cast

import numpy as np
import zarr
from affine import Affine
from numpy.typing import ArrayLike

from ._catalogue import DEFAULT_CATALOGUE, Catalogue
from ._geometry import Geometry, shapes_in_wgs84
from ._grid import BBox, Window
from ._store import DEFAULT_STORE, FloatData, Store, open_store

if TYPE_CHECKING:
    import xarray as xr
    from rasterio.windows import Window as RioWindow

Source: TypeAlias = str | os.PathLike[str] | zarr.Group
MaskedData: TypeAlias = np.ma.MaskedArray[Any, Any]


def _open(source: Source | None, version: str | None, catalogue: str | os.PathLike[str],
          storage_options: dict[str, Any] | None) -> Store:
    if source is not None and version is not None:
        raise ValueError("give source or version, not both")
    if source is None:
        source = Catalogue(catalogue).release(version).url if version is not None else DEFAULT_STORE
    return open_store(source, storage_options=storage_options)


def metadata(source: Source | None = None, *, version: str | None = None,
             catalogue: str | os.PathLike[str] = DEFAULT_CATALOGUE,
             storage_options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the store's dataset attributes as a dictionary, without reading pixels.

    These include ``scenarios``, ``curves``, ``taxa``, ``data_model``, citation,
    and terms of use. Pass a store path or URL, or select a catalogue version.
    With neither, use the published v1.01 store.
    """
    return dict(_open(source, version, catalogue, storage_options).attrs)


def versions(catalogue: str | os.PathLike[str] = DEFAULT_CATALOGUE) -> list[dict[str, Any]]:
    """Return release dictionaries from a catalogue, oldest first.

    Each entry contains ``version``, ``url``, ``path``, ``released``, ``doi``,
    ``description``, and a boolean ``latest`` flag. Unspecified metadata is None.
    """
    manifest = Catalogue(catalogue)
    releases = manifest.releases()
    if not releases:
        return []
    latest = manifest.latest().version
    return [dict(asdict(release), latest=release.version == latest) for release in releases]


def read(layer: str, *, source: Source | None = None, version: str | None = None,
         bounds: Sequence[float] | None = None, window: RioWindow | None = None,
         geometry: Geometry | Iterable[Geometry] | None = None, crs: Any = "EPSG:4326",
         taxon: str | None = "all", level: int = 1, masked: bool = False,
         all_touched: bool = False, catalogue: str | os.PathLike[str] = DEFAULT_CATALOGUE,
         storage_options: dict[str, Any] | None = None) -> tuple[FloatData | MaskedData, Affine]:
    """Return a NumPy array and Affine transform for one region of a LIFE layer.

    Give exactly one of ``bounds`` (west, south, east, north in EPSG:4326),
    an integer-pixel ``rasterio.windows.Window``, or ``geometry`` (Shapely,
    GeoJSON, or a sequence of polygons). Polygon coordinates use ``crs``;
    only the geometry is reprojected, and the returned raster is EPSG:4326.
    Regions are cropped to the grid and cannot wrap across the antimeridian.

    A score band is a 2-D float32 or float64 array. ``taxon=None`` reads all
    bands into a (bands, rows, columns) array; area layers are always 2-D.
    Missing scores are NaN. Zero area is valid data. ``masked=True`` masks
    non-finite values. Geometry reads always return a MaskedArray, masking
    both non-finite values and pixels outside the polygons. Pixel centres
    determine inclusion unless ``all_touched=True``, as in rasterio.

    ``level`` is a resolution factor, with 1 for source resolution. Geometry
    reads require ``life-metric[geo]``. Source and version selection follow
    :func:`metadata`.
    """
    if sum(item is not None for item in (bounds, window, geometry)) != 1:
        raise ValueError("give exactly one of bounds, window, or geometry")
    if geometry is None and (crs != "EPSG:4326" or all_touched):
        raise ValueError("crs and all_touched apply only to geometry reads")
    store = _open(source, version, catalogue, storage_options)
    selected = store.get(layer)
    grid = selected.grid(level)
    shapes = None
    if geometry is not None:
        from rasterio.features import bounds as geometry_bounds

        shapes = shapes_in_wgs84(geometry, crs)
        boxes = [geometry_bounds(shape) for shape in shapes]
        west = max(grid.lon0, min(box[0] for box in boxes))
        south = max(grid.lat0 - grid.height * grid.res, min(box[1] for box in boxes))
        east = min(grid.lon0 + grid.width * grid.res, max(box[2] for box in boxes))
        north = min(grid.lat0, max(box[3] for box in boxes))
        if west >= east or south >= north:
            raise ValueError("geometry does not overlap the store grid")
        win = grid.window(BBox(west, south, east, north))
    elif bounds is not None:
        if len(bounds) != 4:
            raise ValueError("bounds must contain west, south, east, north")
        win = grid.window(BBox(*bounds))
    else:
        assert window is not None
        edges = [float(window.row_off), float(window.col_off),
                 float(window.row_off + window.height), float(window.col_off + window.width)]
        if not all(np.isfinite(edge) and edge.is_integer() for edge in edges):
            raise ValueError("window offsets and sizes must be integer pixels")
        row0, col0, row1, col1 = map(int, edges)
        win = Window(max(0, row0), min(grid.height, row1), max(0, col0), min(grid.width, col1))
        if win.height <= 0 or win.width <= 0:
            raise ValueError("window does not overlap the store grid")
    raster = selected.read(taxon, window=win, level=level)
    transform = Affine.from_gdal(*raster.grid.transform)
    if shapes is not None or masked:
        invalid = ~np.isfinite(raster.data)
        if shapes is not None:
            from rasterio.features import geometry_mask

            outside = geometry_mask(shapes, raster.data.shape[-2:], transform, all_touched=all_touched)
            invalid |= np.broadcast_to(outside, raster.data.shape)
        values = np.ma.array(raster.data, mask=invalid, copy=False,
                             fill_value=np.nan if selected.kind == "score" else 0.0)
        return values, transform
    return raster.data, transform


def sample(layer: str, xy: ArrayLike, *, source: Source | None = None, version: str | None = None,
           taxon: str = "all", level: int = 1,
           catalogue: str | os.PathLike[str] = DEFAULT_CATALOGUE,
           storage_options: dict[str, Any] | None = None) -> FloatData:
    """Return a NumPy array of values for (longitude, latitude) point pairs.

    ``xy`` must have shape (number of points, 2), in EPSG:4326. Coordinates
    must be finite; latitudes outside the grid return NaN and longitudes wrap
    at the antimeridian. Values keep the layer's dtype. Area layers ignore
    ``taxon``. Source and version selection follow :func:`metadata`.
    """
    points = np.asarray(xy, dtype="float64")
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("xy must have shape (number of points, 2), ordered longitude, latitude")
    if not np.isfinite(points).all():
        raise ValueError("point coordinates must be finite")
    store = _open(source, version, catalogue, storage_options)
    return store.get(layer).sample(points[:, 1], points[:, 0], taxon, level=level)


def open_dataset(source: Source | None = None, *, version: str | None = None, level: int = 1,
                 chunks: Any = None, catalogue: str | os.PathLike[str] = DEFAULT_CATALOGUE,
                 storage_options: dict[str, Any] | None = None) -> xr.Dataset:
    """Open a level as a native xarray Dataset with named taxa and a rio accessor.

    Requires ``life-metric[xarray]``. Variables retain their store names,
    dtypes, units, and descriptions. Coordinates are ``lat``, ``lon``, and
    ``taxon``. Dataset attributes include the root metadata, citation, and
    terms. The rio accessor describes EPSG:4326 and the pixel transform.

    With ``chunks=None``, Zarr reads are deferred until values are requested.
    Pass a chunk mapping or ``"auto"`` to use Dask, if installed. Zero changed
    area remains valid data. ``level`` is a reduction factor; use 1 for
    calculations and coarser levels for display. Source and version selection
    follow :func:`metadata`.
    """
    import rioxarray  # noqa: F401; register the standard rio accessor
    import xarray as xr

    store = _open(source, version, catalogue, storage_options)
    selected = store.level(level)
    path = "/".join(part for part in (store._group.path, selected.path) if part)
    dataset = xr.open_zarr(store._group.store, group=path or None, chunks=chunks,
                           zarr_format=3, mask_and_scale=False, decode_coords="all")
    if "taxon" in dataset.coords:
        labels = str(dataset["taxon"].attrs.get("flag_meanings", " ".join(store.taxa))).split()
        dataset = dataset.assign_coords(taxon=("taxon", labels))
        dataset["taxon"].attrs = {"long_name": "species group", "descriptions": dict(store.taxa)}
    dataset.attrs = {**store.attrs, **dataset.attrs}
    dataset.attrs["resolution_factor"] = level
    dataset.attrs["source"] = store.source
    dataset.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
    dataset.rio.write_crs("EPSG:4326", inplace=True)
    dataset.rio.write_transform(Affine.from_gdal(*selected.grid.transform), inplace=True)
    dataset.rio.write_coordinate_system(inplace=True)
    for name in store.layer_names():
        data = dataset[name]
        data.attrs.update(dataset_version=store.version, source=store.source)
        if store.info.citation:
            data.attrs["citation"] = store.info.citation
        if store.info.terms_of_use:
            data.attrs["terms_of_use"] = store.info.terms_of_use
        data.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
        if store.get(name).kind == "score":
            data.rio.write_nodata(np.nan, inplace=True)
        else:
            data.rio.write_nodata(None, inplace=True)
    return cast("xr.Dataset", dataset)
