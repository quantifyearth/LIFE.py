"""Write the LIFE GeoTIFFs into one Zarr v3 store.

Layout, following the zarr-conventions multiscales, proj and spatial
extensions: the root group carries the dataset attributes and the
``multiscales`` layout, and each resolution level is a child group holding
a complete dataset::

    life.zarr/
      zarr.json               root group: attributes, conventions, multiscales layout
      0/                      base level, 21600 x 10800 at 1 arc-minute
        lat, lon              float64 pixel-centre coordinates
        taxon                 int8 index 0..4 with CF flag_values/flag_meanings
        spatial_ref           CF grid-mapping scalar (WKT + GeoTransform)
        arable_0.1 ... arable_gompertz      (taxon, lat, lon) float32
        restore_0.1 ... restore_gompertz    (taxon, lat, lon) float32
        arable_area_changed, restore_area_changed   (lat, lon) float32
      1/ 2/ 3/ 4/             overview levels at factors 2, 4, 8, 16 (see pyramid.py)

The source grid is one row short at each pole; the base level pads one fill
row at each pole so that every level is an exact power-of-two reduction of
the 90N..90S globe with the same origin.

Design constraints found empirically against GDAL 3.12 and zarr-python 3.4:

* GDAL's Zarr driver cannot read the ``sharding_indexed`` codec, nor any v3
  string data type, and its classic raster API cannot index into arrays with
  more than three dimensions. Hence plain chunks, an integer taxon axis with
  labels in attributes, and one 3-D array per (scenario, curve).
* A float64 ``lat``/``lon`` pair named in ``dimension_names`` is enough for
  GDAL to derive the geotransform and for xarray to attach coordinates.
* ``_CRS`` on each array gives GDAL the CRS; ``grid_mapping`` plus the
  ``spatial_ref`` variable gives rioxarray the same.

Rows are converted in blocks aligned to the chunk grid, so every process
touches a disjoint set of chunk files and no locking is needed. Chunks that
are entirely fill value (open ocean) are never written.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import numpy as np
import rasterio
import zarr
from rasterio.crs import CRS
from rasterio.windows import Window
from zarr.codecs import BloscCodec, ZstdCodec

from .. import dataset as L
from ..dataset import Layer

from .. import __version__ as CONVERTER_VERSION


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --- Options ------------------------------------------------------------------


@dataclass
class Options:
    """Chunking, compression and grid settings for a source conversion."""
    chunk: int = 1024
    """Spatial chunk edge in pixels. Row blocks are aligned to this."""
    compressor: str = "zstd"
    """One of ``zstd``, ``blosc-zstd``, ``blosc-lz4``, ``none``."""
    level: int = 5
    workers: int = 8
    height: int = L.HEIGHT
    width: int = L.WIDTH
    row_offset: int = L.ROW_OFFSET
    dtype: str = "float32"
    taxa_descriptions: dict[str, str] | None = None

    @property
    def rows(self) -> int:
        """Rows of the base level, including any polar fill rows."""
        return self.height + 2 * self.row_offset

    def codecs(self) -> list[Any]:
        """Return Zarr codecs selected by the compression settings."""
        if self.compressor == "zstd":
            return [ZstdCodec(level=self.level)]
        if self.compressor == "blosc-zstd":
            return [BloscCodec(cname="zstd", clevel=self.level, shuffle="shuffle")]
        if self.compressor == "blosc-lz4":
            return [BloscCodec(cname="lz4", clevel=self.level, shuffle="shuffle")]
        if self.compressor == "none":
            return []
        raise ValueError(f"unknown compressor {self.compressor!r}")


# --- Store creation -----------------------------------------------------------


def _crs_attrs() -> tuple[str, dict[str, str]]:
    crs = CRS.from_epsg(L.EPSG)
    wkt = crs.to_wkt(version="WKT2_2019")
    gdal = {"url": f"http://www.opengis.net/def/crs/EPSG/0/{L.EPSG}", "wkt": wkt}
    return wkt, gdal


def level_attributes(opts: Options, factor: int, wkt: str) -> dict[str, Any]:
    """Attributes of a level group: its placement, per the proj and spatial conventions."""
    rows, cols = L.level_shape(factor, opts.rows, opts.width)
    res = float(L.level_res(factor))
    return {
        "zarr_conventions": [L.CONVENTIONS["proj"], L.CONVENTIONS["spatial"]],
        "proj:code": f"EPSG:{L.EPSG}",
        "proj:wkt2": wkt,
        "spatial:dimensions": ["lat", "lon"],
        "spatial:transform": L.spatial_transform(factor),
        "spatial:shape": [rows, cols],
        "spatial:bbox": [float(L.LON_MIN), float(L.LAT_TOP) - rows * res, float(L.LON_MIN) + cols * res, float(L.LAT_TOP)],
        "spatial:registration": "pixel",
        "level": L.level_name(factor),
        "factor": factor,
        "resolution_degrees": res,
        "geotransform": list(L.geotransform(factor)),
        "description": (
            f"Base level at {res:g} degrees, {rows} x {cols} pixels, 90N to 90S." if factor == 1 else
            f"Every layer reduced by {factor}: {rows} x {cols} pixels at {res:g} degrees, 90N to 90S. "
            "Each pixel is the mean of the finite pixels of its 2x2 block in the level above. For visualisation."
        ),
    }


def layout_entry(opts: Options, factor: int) -> dict[str, Any]:
    """One ``multiscales.layout`` item for the level of *factor*."""
    rows, cols = L.level_shape(factor, opts.rows, opts.width)
    entry: dict[str, Any] = {"asset": L.level_name(factor)}
    if factor > 1:
        entry["derived_from"] = L.level_name(factor // 2)
        entry["transform"] = {"scale": [2.0, 2.0], "translation": [0.0, 0.0]}
        entry["resampling_method"] = L.RESAMPLING_METHOD
    else:
        entry["transform"] = {"scale": [1.0, 1.0], "translation": [0.0, 0.0]}
    entry["spatial:transform"] = L.spatial_transform(factor)
    entry["spatial:shape"] = [rows, cols]
    return entry


def root_attributes(opts: Options, zip_md5: str | None) -> dict[str, Any]:
    """Return descriptive dataset and convention attributes for the root group."""
    wkt, _ = _crs_attrs()
    rows = opts.rows
    source_transform = list(L.geotransform(1))
    source_transform[3] -= opts.row_offset * float(L.RES)
    return {
        "zarr_conventions": [L.CONVENTIONS["multiscales"], L.CONVENTIONS["proj"], L.CONVENTIONS["spatial"]],
        "multiscales": {"layout": [layout_entry(opts, 1)], "resampling_method": L.RESAMPLING_METHOD},
        "proj:code": f"EPSG:{L.EPSG}",
        "proj:wkt2": wkt,
        "spatial:dimensions": ["lat", "lon"],
        "spatial:transform": L.spatial_transform(1),
        "spatial:shape": [rows, opts.width],
        "spatial:bbox": [float(L.LON_MIN), float(L.LAT_TOP) - rows * float(L.RES), float(L.LON_MIN) + opts.width * float(L.RES), float(L.LAT_TOP)],
        "spatial:registration": "pixel",
        "title": "LIFE: Land-cover change Impacts on Future Extinctions, v1.01",
        "summary": (
            "Global 1 arc-minute maps of the change in expected number of "
            "extinctions of 30,875 terrestrial vertebrate species per km2 of "
            "land converted to arable, or restored to natural habitat, under "
            "five persistence-habitat loss curves, plus the area of land that "
            "changes per pixel under each scenario."
        ),
        "Conventions": "CF-1.11",
        "version": L.ZENODO_VERSION,
        "source_doi": L.ZENODO_DOI,
        "source_url": L.ZENODO_URL,
        "zenodo_record": L.ZENODO_RECORD,
        "concept_doi": L.ZENODO_CONCEPT_DOI,
        "zenodo_records": {k: v for k, v in L.ZENODO_RECORDS.items()},
        "store_path_convention": "v<version>: the dataset version is part of the store URL",
        "published_catalogue": L.PUBLISHED_CATALOGUE,
        "source_archive": L.ZIP_NAME,
        "source_archive_md5": zip_md5,
        "references": L.PAPER_CITATION,
        "paper_doi": L.PAPER_DOI,
        "pipeline": L.PIPELINE_URL,
        "creators": ["Eyres, Alison", "Dales, Michael Winston", "Madhavapeddy, Anil"],
        "terms_of_reference": L.TERMS_OF_REFERENCE,
        "scenarios": dict(L.SCENARIO_DESCRIPTION),
        "curves": dict(L.CURVE_DESCRIPTION),
        "taxa": dict(L.TAXA_LONG),
        "data_model": {
            "score_arrays": "{scenario}_{curve}; dimensions (taxon, lat, lon); units extinctions km-2 of land changed",
            "area_arrays": "{scenario}_area_changed; dimensions (lat, lon); units m2 of land changed within each pixel",
            "taxon_axis": "Integer indices are labelled by taxon.flag_values and taxon.flag_meanings; all is the sum of the four class bands.",
            "missing_data": "Score NaN means no land changes under the scenario; arable scores can also contain -0.0 over ocean. Area zero means no land changes.",
            "pixel_total": "At the base level, score * area_changed / 1e6 gives the maximum change in expected extinctions if all eligible land in that pixel changes.",
            "overviews": "Coarser levels average finite values in each 2x2 block for display. Overview scores and areas are not totals for the larger pixel.",
        },
        "grid": {
            "crs": f"EPSG:{L.EPSG}",
            "resolution_degrees": float(L.RES),
            "width": opts.width,
            "height": rows,
            "geotransform": list(L.geotransform(1)),
            "source_height": opts.height,
            "source_geotransform": source_transform,
            "row_offset": opts.row_offset,
            "note": (
                "The source GeoTIFFs omit one row at each pole (89deg59'N to 89deg59'S). "
                "The store adds one fill row at each pole, so its base level spans 90N to 90S "
                "and source row r is store row r + row_offset. Latitudes and longitudes are pixel centres."
            ) if opts.row_offset else "The source and store both span 90N to 90S; no polar rows are added. Latitudes and longitudes are pixel centres.",
        },
        "history": (
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} "
            f"life-metric {CONVERTER_VERSION}: converted from GeoTIFF with "
            f"chunk={opts.chunk} compressor={opts.compressor} level={opts.level}"
        ),
    }


def create_level(root: zarr.Group, opts: Options, factor: int, which: list[Layer], chunk: int,
                 overwrite: bool = False) -> zarr.Group:
    """Create the group of one level with its coordinates and empty layer arrays."""
    name = L.level_name(factor)
    rows, cols = L.level_shape(factor, opts.rows, opts.width)
    wkt, gdal_crs = _crs_attrs()
    if name in root and not overwrite:
        g = root[name]
        if not isinstance(g, zarr.Group):
            raise TypeError(f"{name} is not a group")
    else:
        g = root.create_group(name, overwrite=overwrite)
        g.attrs.update(level_attributes(opts, factor, wkt))
        lat = g.create_array("lat", data=L.latitudes(rows, factor), dimension_names=("lat",),
                             chunks=(rows,), compressors=opts.codecs())
        lat.attrs.update(standard_name="latitude", long_name="pixel-centre latitude",
                         units="degrees_north", axis="Y")
        lon = g.create_array("lon", data=L.longitudes(cols, factor), dimension_names=("lon",),
                             chunks=(cols,), compressors=opts.codecs())
        lon.attrs.update(standard_name="longitude", long_name="pixel-centre longitude",
                         units="degrees_east", axis="X")
        taxon = g.create_array("taxon", data=np.arange(len(L.TAXA), dtype="int8"), dimension_names=("taxon",),
                               chunks=(len(L.TAXA),), compressors=[])
        taxon.attrs.update(
            long_name="taxonomic group",
            flag_values=list(range(len(L.TAXA))),
            flag_meanings=" ".join(L.TAXA),
            description=dict(opts.taxa_descriptions or L.TAXA_LONG),
        )
        sref = g.create_array("spatial_ref", shape=(), dtype="int32", fill_value=0, compressors=[])
        sref[...] = 0
        sref.attrs.update(
            grid_mapping_name="latitude_longitude",
            crs_wkt=wkt,
            spatial_ref=wkt,
            GeoTransform=" ".join(repr(v) for v in L.geotransform(factor)),
            longitude_of_prime_meridian=0.0,
            semi_major_axis=6378137.0,
            inverse_flattening=298.257223563,
        )
    for layer in which:
        if layer.name in g and not overwrite:
            continue
        shape: tuple[int, ...]
        chunks: tuple[int, ...]
        if layer.kind == "life":
            shape, chunks = (len(layer.bands), rows, cols), (1, chunk, chunk)
        else:
            shape, chunks = (rows, cols), (chunk, chunk)
        arr = g.create_array(
            layer.name, shape=shape, chunks=chunks, dtype=opts.dtype,
            fill_value=layer.fill_value, dimension_names=layer.dims,
            compressors=opts.codecs(), overwrite=overwrite,
            config={"write_empty_chunks": False},
        )
        attrs: dict[str, Any] = {
            "long_name": layer.long_name,
            "units": layer.units,
            "description": layer.description,
            "scenario": layer.scenario,
            "kind": "score" if layer.kind == "life" else "area",
            "source_file": layer.source,
            "source_bands": list(layer.bands),
            "grid_mapping": "spatial_ref",
            "spatial:dimensions": ["lat", "lon"],
            "_CRS": gdal_crs,
            "level": name,
            "factor": factor,
        }
        if layer.kind == "life" and layer.curve is not None:
            attrs["curve"] = layer.curve
            attrs["z"] = L.CURVE_Z[layer.curve]
            attrs["taxon_labels"] = list(layer.bands)
            attrs["related_area_layer"] = f"{layer.scenario}_area_changed"
            attrs["band_relation"] = "The all band is the sum of AMPHIBIA, AVES, MAMMALIA and REPTILIA."
            attrs["missing_data"] = (
                "NaN means no land changes under this scenario; -0.0 may occur over ocean."
                if layer.scenario == "arable" else
                "NaN means no land changes under this scenario."
            )
        else:
            attrs["missing_data"] = "Zero means no land changes under this scenario."
        if factor > 1:
            attrs["resampling"] = (
                "Mean of finite pixels in each 2x2 block of the level above; NaN where all are missing. "
                "For display, not a score for the larger area." if layer.kind == "life" else
                "Mean of finite pixels in each 2x2 block of the level above; NaN where all are missing, "
                "zero where all are zero. "
                "For display, not the total changed area of the larger pixel."
            )
            attrs["resampling_method"] = L.RESAMPLING_METHOD
        arr.attrs.update(attrs)
    return g


def set_layout(root: zarr.Group, opts: Options, factors: list[int]) -> None:
    """Write the ``multiscales`` layout for the base level and *factors*, in order."""
    root.attrs["multiscales"] = {
        "layout": [layout_entry(opts, f) for f in [1, *sorted(factors)]],
        "resampling_method": L.RESAMPLING_METHOD,
    }


def create_store(
    store_path: Path,
    opts: Options,
    which: list[Layer] | None = None,
    overwrite: bool = False,
    zip_md5: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> zarr.Group:
    """Create the root group with its conventions and the base level ``0``."""
    which = which or list(L.LAYERS)
    root = zarr.create_group(store_path, zarr_format=3, overwrite=overwrite)
    root.attrs.update(attributes if attributes is not None else root_attributes(opts, zip_md5))
    create_level(root, opts, 1, which, opts.chunk, overwrite=overwrite)
    return root


# --- Block conversion (runs in worker processes) --------------------------------


@dataclass
class BandStats:
    """Accumulated finite-value statistics for one band."""
    n_valid: int = 0
    n_nonzero: int = 0
    min: float = float("inf")
    max: float = float("-inf")
    sum: float = 0.0

    def merge(self, other: BandStats) -> None:
        """Add statistics from another block of the same band."""
        self.n_valid += other.n_valid
        self.n_nonzero += other.n_nonzero
        self.min = min(self.min, other.min)
        self.max = max(self.max, other.max)
        self.sum += other.sum

    def finish(self) -> dict[str, Any]:
        """Return JSON-ready statistics for the completed band."""
        d = asdict(self)
        if self.n_valid == 0:
            d["min"] = d["max"] = None
            d["mean"] = None
        else:
            d["mean"] = self.sum / self.n_valid
        return d


def _band_stats(block: np.ndarray) -> BandStats:
    valid = np.isfinite(block)
    n = int(valid.sum())
    if n == 0:
        return BandStats()
    v = block[valid]
    return BandStats(
        n_valid=n,
        n_nonzero=int(np.count_nonzero(v)),
        min=float(v.min()),
        max=float(v.max()),
        sum=float(v.sum(dtype="float64")),
    )


def convert_block(store_path: str, name: str, tif: str, row0: int, row1: int,
                  row_offset: int = L.ROW_OFFSET) -> tuple[int, int, list[BandStats]]:
    """Copy store rows [row0, row1) of every band from *tif* into level-0 array *name*.

    Store row r holds source row r - row_offset; any polar fill rows are skipped.
    """
    zarr.config.set({"array.write_empty_chunks": False})
    with rasterio.open(tif) as src:
        s0, s1 = max(0, row0 - row_offset), min(src.height, row1 - row_offset)
        block = src.read(window=Window(0, s0, src.width, s1 - s0))
    arr = zarr.open_array(store_path, path=f"{L.level_name(1)}/{name}", mode="r+")
    t0, t1 = s0 + row_offset, s1 + row_offset
    if arr.ndim == 2:
        arr[t0:t1, :] = block[0]
    else:
        arr[:, t0:t1, :] = block
    return row0, row1, [_band_stats(b) for b in block]


def row_blocks(rows: int, size: int) -> list[tuple[int, int]]:
    """Half-open row ranges of *size* covering *rows*, aligned to the chunk grid."""
    return [(r, min(r + size, rows)) for r in range(0, rows, size)]


# --- Driver ---------------------------------------------------------------------


@dataclass
class LayerReport:
    """Conversion result for one source layer."""
    name: str
    seconds: float
    bands: dict[str, dict[str, Any]] = field(default_factory=dict)


def convert_layers(
    store_path: Path,
    raw_dir: Path,
    which: list[Layer],
    opts: Options,
) -> list[LayerReport]:
    """Convert *which* layers using a process pool, then record per-band stats."""
    reports: list[LayerReport] = []
    with ProcessPoolExecutor(max_workers=opts.workers) as pool:
        for layer in which:
            tif = raw_dir / layer.source
            if not tif.exists():
                raise FileNotFoundError(f"{tif} missing; run `life-metric extract` first")
            with rasterio.open(tif) as src:
                if (src.height, src.width, src.count) != (opts.height, opts.width, len(layer.bands)):
                    raise RuntimeError(
                        f"{tif}: shape {(src.height, src.width, src.count)} does not match "
                        f"expected {(opts.height, opts.width, len(layer.bands))}"
                    )
            t0 = time.monotonic()
            blocks = row_blocks(opts.rows, opts.chunk)
            futures = [
                pool.submit(convert_block, str(store_path), layer.name, str(tif), r0, r1, opts.row_offset)
                for r0, r1 in blocks
            ]
            totals = [BandStats() for _ in layer.bands]
            done = 0
            for fut in as_completed(futures):
                _, _, stats = fut.result()
                for t, s in zip(totals, stats):
                    t.merge(s)
                done += 1
                _log(f"  {layer.name}: {done}/{len(blocks)} blocks")
            secs = time.monotonic() - t0
            report = LayerReport(layer.name, secs, {b: s.finish() for b, s in zip(layer.bands, totals)})
            arr = zarr.open_array(store_path, path=f"{L.level_name(1)}/{layer.name}", mode="r+")
            arr.attrs["statistics"] = report.bands
            arr.attrs["chunks_written"] = arr.nchunks_initialized
            arr.attrs["chunks_total"] = arr.nchunks
            reports.append(report)
            _log(
                f"{layer.name}: done in {secs:.0f}s, "
                f"{arr.nchunks_initialized}/{arr.nchunks} chunks stored"
            )
    return reports


def finalize(store_path: Path) -> None:
    """Consolidate metadata at the root and at every level, so any of them opens with one read."""
    root = zarr.open_group(store_path, mode="r+", use_consolidated=False)
    for entry in layout_of(root):
        if entry["asset"] in root:
            zarr.consolidate_metadata(store_path, path=str(entry["asset"]))
    zarr.consolidate_metadata(store_path)


def layout_of(root: zarr.Group) -> list[dict[str, Any]]:
    """Return the ``multiscales.layout`` entries of a root group, or an empty list."""
    ms = cast(dict[str, Any], root.attrs.get("multiscales") or {})
    return [dict(e) for e in ms.get("layout", [])]


def describe(store_path: Path) -> str:
    """Return a readable summary of a converted store."""
    root = zarr.open_group(store_path, mode="r")
    lines = [f"{store_path}", json.dumps({k: v for k, v in root.attrs.items() if k not in ("proj:wkt2", "multiscales")}, indent=2)[:2000], ""]
    for entry in layout_of(root):
        name = str(entry["asset"])
        if name not in root:
            lines.append(f"level {name}: missing")
            continue
        g = root[name]
        if not isinstance(g, zarr.Group):
            continue
        lines.append(f"level {name}: shape {entry.get('spatial:shape')} transform {entry.get('spatial:transform')}")
        for aname, arr in sorted(g.arrays()):
            if aname in ("lat", "lon", "taxon", "spatial_ref"):
                continue
            lines.append(
                f"  {aname:22s} {str(arr.shape):22s} chunks={arr.chunks} stored={arr.nchunks_initialized}/{arr.nchunks} "
                f"bytes={arr.nbytes_stored() / 1e6:.1f}MB"
            )
            stats = cast(dict[str, dict[str, Any]], arr.attrs.get("statistics") or {})
            if stats and name == "0":
                for band, s in stats.items():
                    lines.append(
                        f"      {band:10s} valid={s['n_valid']:>10d} nonzero={s['n_nonzero']:>10d} "
                        f"min={s['min']!s:>14} max={s['max']!s:>14} mean={s['mean']!s}"
                    )
    return "\n".join(lines)
