"""Query, download and inspect LIFE Zarr data; maintain stores with admin tools."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.table import Table
from rich_argparse import RichHelpFormatter

from . import __version__
from . import dataset as L
from ._catalogue import DEFAULT_CATALOGUE, Catalogue
from ._grid import BBox
from ._store import Layer, Store, open_store
from .dataset import FACTORS

console = Console()
error_console = Console(stderr=True)


class _Parser(argparse.ArgumentParser):
    """Use Rich formatting for command and subcommand help."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", RichHelpFormatter)
        super().__init__(*args, **kwargs)


def _layers(names: list[str] | None) -> list[L.Layer]:
    if not names:
        return list(L.LAYERS)
    return [L.layer_by_name(n) for n in names]


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data-dir", type=Path, default=Path("data"),
                   help="directory holding raw/ (the zip and GeoTIFFs); default ./data")
    p.add_argument("--version", default=L.ZENODO_VERSION,
                   help=f"dataset version, which names the store directory (default {L.ZENODO_VERSION})")
    p.add_argument("--store", type=Path, default=None,
                   help="zarr store path; default <data-dir>/v<version>")


def _resolve(args: argparse.Namespace) -> tuple[Path, Path]:
    raw = args.data_dir / "raw"
    store = args.store or L.store_path(args.data_dir, args.version)
    return raw, store


def _reader_source(args: argparse.Namespace) -> str:
    """Choose an explicit source, a local version, or its published URL."""
    if args.source:
        return str(args.source)
    if args.store:
        return str(args.store)
    _, store = _resolve(args)
    return str(store) if store.exists() else f"{DEFAULT_CATALOGUE}/v{args.version}"


def _add_reader_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", nargs="?", help="store directory or URL (default: local version if present, else published)")
    parser.add_argument("--version", default=L.ZENODO_VERSION,
                        help="dataset version to open (default: %(default)s)")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help=argparse.SUPPRESS)
    parser.add_argument("--store", help=argparse.SUPPRESS)


def cmd_download(args: argparse.Namespace) -> int:
    """Fetch the Zenodo archive and optionally extract its GeoTIFFs."""
    from .build.download import download, extract

    raw, _ = _resolve(args)
    with Progress(TextColumn("{task.description}"), BarColumn(), DownloadColumn(),
                  TransferSpeedColumn(), TimeRemainingColumn(), console=error_console) as progress:
        task = progress.add_task("Downloading", total=L.ZIP_SIZE)

        def update(done: int, total: int) -> None:
            progress.update(task, completed=done, total=total)

        zip_path = download(raw, expected_md5=None if args.no_verify else L.ZIP_MD5, on_progress=update)
    if not args.no_extract:
        extract(zip_path, raw)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract selected files from an archive already on disk."""
    from .build.download import extract

    raw, _ = _resolve(args)
    extract(raw / L.ZIP_NAME, raw, names=[l.source for l in _layers(args.layers)] or None)
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    """Create or extend the base level from source GeoTIFFs."""
    from .build.convert import Options, convert_layers, create_level, create_store, finalize

    raw, store = _resolve(args)
    which = _layers(args.layers)
    opts = Options(chunk=args.chunk, compressor=args.compressor, level=args.level, workers=args.workers)
    zip_path = raw / L.ZIP_NAME
    zip_md5 = L.ZIP_MD5 if zip_path.exists() else None
    if args.append:
        if not store.exists():
            raise ValueError(f"{store} does not exist; drop --append")
        import zarr
        root = zarr.open_group(store, mode="r+")
        # The layers live in the base-level group, not at the root.
        create_level(root, opts, 1, which, opts.chunk)
    else:
        if store.exists() and not args.overwrite:
            raise ValueError(f"{store} exists; pass --overwrite or --append")
        create_store(store, opts, which=which, overwrite=True, zip_md5=zip_md5)
    convert_layers(store, raw, which, opts)
    finalize(store)
    console.print(f"Converted {len(which)} layers into {store}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Compare base-level cells against the source GeoTIFFs."""
    from .build.verify import verify_layers

    raw, store = _resolve(args)
    results = verify_layers(store, raw, _layers(args.layers), workers=args.workers,
                            rows=args.rows, gdal=args.gdal)
    table = Table(title="Source comparison")
    for column in ("Layer", "Blocks", "Mismatches", "GDAL", "Result"):
        table.add_column(column)
    for result in results:
        table.add_row(result.name, str(result.blocks), str(result.mismatched_cells),
                      "—" if result.gdal_ok is None else "OK" if result.gdal_ok else "FAIL",
                      "OK" if result.ok else "FAIL")
    console.print(table)
    return 0 if all(result.ok for result in results) else 1


def cmd_pyramid(args: argparse.Namespace) -> int:
    """Build downsampled overview levels."""
    from .build.convert import Options, finalize
    from .build.pyramid import build_pyramid, create_pyramid

    _, store = _resolve(args)
    which = _layers(args.layers)
    factors = tuple(int(f) for f in args.factors.split(","))
    opts = Options(compressor=args.compressor, level=args.level, workers=args.workers)
    create_pyramid(store, opts, which, factors=factors, chunk=args.chunk, overwrite=args.overwrite)
    build_pyramid(store, which, factors=factors, workers=args.workers)
    finalize(store)
    return 0


def cmd_viewer(args: argparse.Namespace) -> int:
    """Install the bundled browser viewer into a store directory."""
    from .viewer import install_viewer

    _, store = _resolve(args)
    for p in install_viewer(store, lib_dir=args.lib):
        print(f"installed {p}")
    rel = store.relative_to(args.data_dir) if store.is_relative_to(args.data_dir) else store
    print(f"serve it with:  python3 -m http.server -d {args.data_dir} 8000   then open http://localhost:8000/{rel}/index.html?store=.")
    return 0


def cmd_catalogue(args: argparse.Namespace) -> int:
    """Write a release entry into the local versions.json manifest."""
    from .build.manifest import write_manifest

    _, store = _resolve(args)
    manifest = write_manifest(args.data_dir, store, released=args.released, description=args.description, latest=args.latest)
    print(f"wrote {args.data_dir / 'versions.json'}: versions {list(manifest['versions'])}, latest {manifest['latest']}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Describe a store using its own metadata and layer attributes."""
    store = open_store(_reader_source(args))
    if args.json:
        data = {"source": store.source, "info": vars(store.info), "scenarios": store.scenarios,
                "curves": store.curves, "taxa": store.taxa, "data_model": store.data_model,
                "levels": [{"factor": f, "path": store.level(f).path,
                            "shape": [store.level_grid(f).height, store.level_grid(f).width]}
                           for f in store.levels],
                "layers": [{"name": layer.name, "kind": layer.kind, "bands": layer.bands,
                            "units": layer.units, "description": layer.description}
                           for layer in store.layers()]}
        print(json.dumps(data, indent=2, allow_nan=False))
    else:
        console.print(store.describe(), markup=False, highlight=False)
    return 0


def cmd_releases(args: argparse.Namespace) -> int:
    """List stores in a local or published catalogue."""
    catalogue = Catalogue(args.catalogue)
    releases = catalogue.releases()
    latest = catalogue.latest().version
    if args.json:
        print(json.dumps({"latest": latest, "versions": [vars(release) for release in releases]}, indent=2))
    else:
        table = Table(title=f"LIFE releases: {catalogue.base}")
        for column in ("Version", "Released", "Store", "Latest"):
            table.add_column(column)
        for release in releases:
            table.add_row(release.version, release.released or "—", release.url,
                          "yes" if release.version == latest else "")
        console.print(table)
    return 0


def _selected_layer(store: Store, args: argparse.Namespace) -> Layer:
    """Choose a layer and report valid names from the opened store."""
    if args.scenario not in store.scenarios:
        raise ValueError(f"unknown scenario {args.scenario!r}; choose from {', '.join(store.scenarios)}")
    if args.area:
        return store.area(args.scenario)
    if args.curve not in store.curves:
        raise ValueError(f"unknown curve {args.curve!r}; choose from {', '.join(store.curves)}")
    if args.taxon not in store.taxa:
        raise ValueError(f"unknown taxon {args.taxon!r}; choose from {', '.join(store.taxa)}")
    return store.layer(args.scenario, args.curve)


def cmd_sample(args: argparse.Namespace) -> int:
    """Read a score or changed-area value at one point through Zarr."""
    store = open_store(_reader_source(args))
    layer = _selected_layer(store, args)
    value = layer.value(args.lat, args.lon, args.taxon, level=args.level)
    result = {"version": store.version, "layer": layer.name, "scenario": layer.scenario,
              "curve": layer.curve, "taxon": "area" if args.area else args.taxon,
              "lat": args.lat, "lon": args.lon, "level": args.level,
              "value": value if math.isfinite(value) else None, "units": layer.units}
    if args.json:
        print(json.dumps(result, allow_nan=False))
    else:
        table = Table(title=f"{layer.long_name} (version {store.version})")
        for column in ("Location", "Band", "Value", "Units"):
            table.add_column(column)
        table.add_row(f"{args.lat:g}, {args.lon:g}", str(result["taxon"]),
                      f"{value:.9g}" if math.isfinite(value) else "no data", layer.units)
        console.print(table)
    return 0


def cmd_download_region(args: argparse.Namespace) -> int:
    """Save a bounded layer read from Zarr as a compressed NumPy archive."""
    output: Path = args.output
    if output.suffix != ".npz":
        raise ValueError("the output path must end in .npz")
    if output.exists() and not args.overwrite:
        raise ValueError(f"{output} exists; pass --overwrite to replace it")
    store = open_store(_reader_source(args))
    layer = _selected_layer(store, args)
    bbox = BBox(*args.bbox)
    window = layer.grid(args.level).window(bbox)
    bands = 1 if args.area or not args.all_bands else len(layer.bands)
    if window.height * window.width * bands > 16_000_000:
        raise ValueError("the region is too large for one download; select a smaller bounding box")
    raster = layer.read(None if args.all_bands and not args.area else args.taxon,
                        bbox=bbox, level=args.level)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"version": store.version, "source": store.source, "layer": layer.name,
                "bands": raster.bands, "units": layer.units, "level": args.level,
                "bounds": vars(raster.grid.bounds)}
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.",
                                         suffix=".npz", delete=False) as temp:
            temp_path = Path(temp.name)
            np.savez_compressed(temp, data=raster.data, lat=raster.grid.latitudes(),
                                lon=raster.grid.longitudes(), metadata=json.dumps(metadata))
        os.replace(temp_path, output)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    console.print(f"Saved {layer.name} {raster.data.shape} to {output}")
    return 0


def cmd_md5(args: argparse.Namespace) -> int:
    """Print MD5 digests for local files."""
    from .build.download import md5sum

    for p in args.paths:
        print(f"{md5sum(p)}  {p}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Return the complete parser for reader and builder commands."""
    p = _Parser(prog="life-metric", description=__doc__)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)

    i = sub.add_parser("info", help="describe a store and its layers")
    _add_reader_source(i)
    i.add_argument("--json", action="store_true", help="write machine-readable JSON")
    i.set_defaults(func=cmd_info)

    r = sub.add_parser("releases", help="list stores in a versions.json catalogue")
    r.add_argument("--catalogue", default=DEFAULT_CATALOGUE, help="catalogue directory or URL")
    r.add_argument("--json", action="store_true", help="write machine-readable JSON")
    r.set_defaults(func=cmd_releases)

    s = sub.add_parser("query", aliases=["sample"], help="query one score or changed-area value at a point")
    s.add_argument("lat", type=float, help="latitude in degrees")
    s.add_argument("lon", type=float, help="longitude in degrees")
    _add_reader_source(s)
    s.add_argument("--scenario", default="arable", help="scenario name (default: arable)")
    s.add_argument("--curve", default="0.25", help="persistence curve (default: 0.25)")
    s.add_argument("--taxon", default="all", help="species group (default: all)")
    s.add_argument("--level", type=int, default=1, help="resolution factor (default: 1)")
    s.add_argument("--area", action="store_true", help="query changed area in m² instead of a score")
    s.add_argument("--json", action="store_true", help="write one JSON object; missing values become null")
    s.set_defaults(func=cmd_sample)

    download = sub.add_parser("download", help="save a bounded layer from a store as .npz")
    download.add_argument("output", type=Path, help="output .npz file")
    _add_reader_source(download)
    download.add_argument("--bbox", nargs=4, type=float, required=True,
                          metavar=("WEST", "SOUTH", "EAST", "NORTH"), help="region in degrees")
    download.add_argument("--scenario", default="arable", help="scenario name (default: arable)")
    download.add_argument("--curve", default="0.25", help="persistence curve (default: 0.25)")
    download.add_argument("--taxon", default="all", help="species group (default: all)")
    download.add_argument("--all-bands", action="store_true", help="include all score bands")
    download.add_argument("--level", type=int, default=1, help="resolution factor (default: 1)")
    download.add_argument("--area", action="store_true", help="download changed area in m²")
    download.add_argument("--overwrite", action="store_true", help="replace an existing output file")
    download.set_defaults(func=cmd_download_region)

    admin = sub.add_parser("admin", help="build and maintain Zarr stores from GeoTIFFs")
    admin_sub = admin.add_subparsers(dest="admin_cmd", required=True, parser_class=_Parser)

    d = admin_sub.add_parser("download-zenodo", help="fetch and extract the raw v1.01 Zenodo archive")
    _add_common(d)
    d.add_argument("--no-verify", action="store_true", help="skip the md5 check")
    d.add_argument("--no-extract", action="store_true", help="only download")
    d.set_defaults(func=cmd_download)

    e = admin_sub.add_parser("extract", help="unpack the GeoTIFFs from an already downloaded zip")
    _add_common(e)
    e.add_argument("layers", nargs="*", help="layer names to extract (default all)")
    e.set_defaults(func=cmd_extract)

    c = admin_sub.add_parser("convert", help="write the GeoTIFFs into a zarr v3 store")
    _add_common(c)
    c.add_argument("layers", nargs="*", help="layer names to convert (default all)")
    c.add_argument("--chunk", type=int, default=1024, help="spatial chunk edge in pixels (default 1024)")
    c.add_argument("--compressor", default="zstd", choices=["zstd", "blosc-zstd", "blosc-lz4", "none"])
    c.add_argument("--level", type=int, default=5, help="compression level (default 5)")
    c.add_argument("--workers", type=int, default=8, help="worker processes (default 8)")
    c.add_argument("--overwrite", action="store_true", help="replace an existing store")
    c.add_argument("--append", action="store_true", help="add layers to an existing store")
    c.set_defaults(func=cmd_convert)

    v = admin_sub.add_parser("verify", help="compare the store against the source GeoTIFFs")
    _add_common(v)
    v.add_argument("layers", nargs="*", help="layer names to verify (default all)")
    v.add_argument("--workers", type=int, default=8)
    v.add_argument("--rows", type=int, default=1024, help="rows per comparison block")
    v.add_argument("--gdal", action="store_true", help="also read windows through GDAL's Zarr driver")
    v.set_defaults(func=cmd_verify)

    y = admin_sub.add_parser("pyramid", help="add downsampled overview levels for visualisation")
    _add_common(y)
    y.add_argument("layers", nargs="*", help="layer names (default all)")
    y.add_argument("--factors", default=",".join(str(f) for f in FACTORS),
                   help="comma separated powers of two (default %(default)s)")
    y.add_argument("--chunk", type=int, default=512, help="chunk edge for the levels (default 512)")
    y.add_argument("--compressor", default="zstd", choices=["zstd", "blosc-zstd", "blosc-lz4", "none"])
    y.add_argument("--level", type=int, default=5)
    y.add_argument("--workers", type=int, default=8)
    y.add_argument("--overwrite", action="store_true", help="rebuild levels that already exist")
    y.set_defaults(func=cmd_pyramid)

    w = admin_sub.add_parser("viewer", help="copy the browser viewer (index.html and the life-metric library) into the store")
    _add_common(w)
    w.add_argument("--lib", type=Path, default=None,
                   help="built dist/ directory of the life-metric TypeScript package to install instead of the bundled copy")
    w.set_defaults(func=cmd_viewer)

    k = admin_sub.add_parser("catalogue", help="add the store to <data-dir>/versions.json for the client libraries")
    _add_common(k)
    k.add_argument("--released", help="release date to record, e.g. 2024-12-19")
    k.add_argument("--description", help="one line describing the release")
    k.add_argument("--latest", help="version to mark as latest (default: highest)")
    k.set_defaults(func=cmd_catalogue)

    m = admin_sub.add_parser("md5", help="md5 of files (helper)")
    m.add_argument("paths", nargs="+", type=Path)
    m.set_defaults(func=cmd_md5)
    return p


def main(argv: list[str] | None = None) -> None:
    """Run a command and exit with its status code."""
    args = build_parser().parse_args(argv)
    try:
        status = args.func(args)
    except ModuleNotFoundError as exc:
        if exc.name != "rasterio":
            raise
        error_console.print("Error: install life-metric[build] to use admin commands")
        status = 1
    except (FileNotFoundError, KeyError, ValueError, OSError, RuntimeError) as exc:
        error_console.print(f"Error: {exc}", markup=False, highlight=False)
        status = 1
    sys.exit(status)
