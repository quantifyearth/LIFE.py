import os
from contextlib import contextmanager
from pathlib import Path

import aiohttp
import numpy as np
import pytest

from life_metric import open_dataset
from life_metric._catalogue import Catalogue
from life_metric._grid import BBox, Grid, Window
from life_metric._store import open_store
from tests.conftest import H, RES, W, band_values


def test_open_describes_from_attrs(store_path: Path) -> None:
    store = open_store(store_path)
    assert store.version == "0.9"
    assert list(store.scenarios) == ["arable", "restore"] and store.scenarios["arable"] == "conversion"
    assert list(store.curves) == ["0.25", "gompertz"]  # fewer than the real dataset: read from the store, not hardcoded
    assert list(store.taxa) == ["all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA"]
    assert store.info.version == "0.9" and store.info.title == "LIFE"
    assert store.levels == (1, 2)
    assert store.grid == Grid(W, H, RES, -180.0, 90.0)
    assert store.level(2).path == "1" and store.level(2).grid == Grid(W // 2, H // 2, 2 * RES, -180.0, 90.0)
    assert "0" in store.path(1, "arable_0.25")
    assert store.layer_names() == ["arable_0.25", "arable_gompertz", "restore_0.25", "restore_gompertz",
                                   "arable_area_changed", "restore_area_changed"]
    assert len(store.layers()) == 6
    assert "version 0.9" in store.describe() and "conversion" in store.describe()
    with pytest.raises(KeyError):
        store.layer("arable", "0.5")


def test_layer_metadata(store_path: Path) -> None:
    layer = open_store(store_path).layer("arable", "0.25")
    assert layer.kind == "score" and layer.bands[1] == "AMPHIBIA" and layer.units == "extinctions km-2"
    assert layer.scenario_description == "conversion" and layer.curve_description == "main"
    assert layer.summary.startswith("arable_0.25: change in expected extinctions")
    assert layer.shape() == (5, H, W) and layer.shape(2) == (5, H // 2, W // 2)
    assert np.isnan(layer.fill_value)
    area = open_store(store_path).area("restore")
    assert area.kind == "area" and area.bands == ("area",) and area.fill_value == 0.0


def test_layer_with_underscored_scenario(tmp_path: Path) -> None:
    import zarr

    root = zarr.create_group(tmp_path / "beta", zarr_format=3)
    root.attrs.update({
        "scenarios": {"restore_all": "broader restoration"},
        "curves": {"0.25": "power law"},
        "taxa": {name: name for name in ("all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA")},
        "multiscales": {"layout": [{"asset": "0", "transform": {"scale": [1, 1]},
                                   "spatial:transform": [90, 0, -180, 0, -90, 90], "spatial:shape": [2, 4]}]},
    })
    group = root.create_group("0")
    arr = group.create_array("restore_all_0.25", shape=(5, 2, 4), chunks=(1, 2, 4),
                             dtype="float64", fill_value=np.nan)
    arr[0, 0, 0] = 0.123456789012345
    arr.attrs.update({"scenario": "restore_all", "curve": "0.25", "kind": "score",
                      "taxon_labels": ["all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA"]})

    layer = open_store(root).layer("restore_all", "0.25")
    assert (layer.scenario, layer.curve, layer.kind) == ("restore_all", "0.25", "score")
    assert layer.scenario_description == "broader restoration"
    assert layer.shape() == (5, 2, 4)
    raster = layer.read(window=Window(0, 1, 0, 1))
    assert raster.data.dtype == np.dtype("float64")
    assert raster.data[0, 0] == 0.123456789012345
    samples = layer.sample([45, 91], [-135, -135])
    assert samples.dtype == np.dtype("float64")
    assert samples[0] == 0.123456789012345 and np.isnan(samples[1])


def test_missing_store_descriptions_are_reported(tmp_path: Path) -> None:
    import zarr

    root = zarr.create_group(tmp_path / "missing-metadata", zarr_format=3)
    with pytest.raises(ValueError, match="scenario descriptions"):
        open_store(root)


def test_read_bbox_and_window(store_path: Path) -> None:
    layer = open_store(store_path).layer("arable", "0.25")
    expect = band_values(2, 1.0)
    r = layer.read("AVES", bbox=BBox(-90, 0, 0, 45))  # cols 6..12, rows 3..6 (90N is row 0)
    assert r.grid.bounds == BBox(-90, 0, 0, 45)
    assert np.array_equal(r.data, expect[3:6, 6:12], equal_nan=True)
    assert r.bands == ("AVES",) and r.level == 1
    w = layer.read("AVES", window=Window(3, 6, 6, 12))
    assert np.array_equal(w.data, r.data, equal_nan=True)
    whole = layer.read("AVES")
    assert whole.data.shape == (H, W)
    stack = layer.read(None, bbox=BBox(-90, 0, 0, 45))
    assert stack.is_stack and stack.data.shape == (5, 3, 6)
    assert np.array_equal(stack.band("AVES"), r.data, equal_nan=True)


def test_value_and_sample(store_path: Path) -> None:
    layer = open_store(store_path).layer("restore", "gompertz")
    expect = band_values(0, -1.0)
    grid = layer.grid()
    lat, lon = grid.latitudes()[4], grid.longitudes()[7]
    assert layer.value(lat, lon) == expect[4, 7]
    assert np.isnan(layer.value(grid.latitudes()[0], lon))  # NaN row
    assert np.isnan(layer.value(91.0, 0.0))  # off the grid
    lats = grid.latitudes()[[1, 4, 11]]
    lons = grid.longitudes()[[0, 7, 23]]
    got = layer.sample(lats, lons, "MAMMALIA")
    want = np.array([band_values(3, -1.0)[r, c] for r, c in zip([1, 4, 11], [0, 7, 23])])
    assert np.array_equal(got, want)
    # longitude wraps
    assert layer.value(lat, lon + 360) == expect[4, 7]


def test_overview_level(store_path: Path) -> None:
    layer = open_store(store_path).layer("arable", "0.25")
    g2 = layer.grid(2)
    assert (g2.width, g2.height, g2.res, g2.lat0) == (12, 6, 30.0, 90.0)
    r = layer.read("all", level=2)
    assert r.data.shape == (6, 12)
    # a level-2 pixel is the mean of the finite base pixels beneath it
    base = band_values(0, 1.0)
    block = base[2:4, 2:4]  # base rows 2,3 and cols 2,3 -> level pixel (1, 1)
    assert r.data[1, 1] == pytest.approx(np.nanmean(block))
    assert layer.value(90 - 45, -180 + 45, level=2) == r.data[1, 1]
    with pytest.raises(ValueError):
        layer.read(level=4)


def test_area_layer(store_path: Path) -> None:
    area = open_store(store_path).area("arable")
    r = area.read(bbox=BBox(0, -45, 90, 45))
    assert r.data.shape == (6, 6) and r.bands == ("area",)
    assert area.value(0.5, 0.5) == r.data[2, 0]  # 0.5N is the third row of a box starting at 45N


def test_catalogue(catalogue_dir: Path) -> None:
    cat = Catalogue(catalogue_dir)
    versions = [r.version for r in cat.releases()]
    assert versions == ["0.9", "0.10"]  # numeric order, not string order
    assert cat.latest().version == "0.9"  # the manifest says so
    rel = cat.release("0.10")
    assert rel.url == str(catalogue_dir / "v0.10/life.zarr") and rel.released == "2026-06-01"
    store = cat.open()
    assert store.version == "0.9"
    with pytest.raises(KeyError):
        cat.release("2.0")


def test_xarray(store_path: Path) -> None:
    xr = pytest.importorskip("xarray")
    store = open_store(store_path)
    ds = open_dataset(store_path)
    assert list(ds["taxon"].values) == ["all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA"]
    import zarr
    ds2 = open_dataset(zarr.open_group(store_path, mode="r"), level=2)  # opened from a group, not a path
    assert ds2["arable_0.25"].shape == (5, H // 2, W // 2)
    assert ds["arable_0.25"].sel(taxon="AVES").shape == (H, W)
    da = ds["arable_0.25"].sel(taxon="AVES")
    assert isinstance(da, xr.DataArray) and da.dims == ("lat", "lon")


REAL_DATA = Path(os.environ.get("LIFE_DATA", "/home/avsm2/src/git/avsm/life/data"))
REAL = REAL_DATA / "v1.01"


@pytest.mark.skipif(not REAL.exists(), reason="real store not present")
def test_real_store() -> None:
    store = open_store(REAL)
    assert store.version == "1.01" and store.levels == (1, 2, 4, 8, 16)
    assert store.info.doi == "10.5281/zenodo.14945383" and "IBAT" in (store.info.terms_of_use or "")
    assert store.level(2).resampling_method == "average" and store.level(1).resampling_method is None
    assert "extinction" in store.taxa["all"].lower() or "vertebrates" in store.taxa["all"]
    assert store.grid == Grid(21600, 10800, 1 / 60, -180.0, 90.0)
    assert [store.level(f).path for f in store.levels] == ["0", "1", "2", "3", "4"]
    assert len(store.layers()) == 12
    layer = store.layer("arable", "0.25")
    grid = layer.grid()
    # source row 5099 is store row 5100 (one fill row was added at the north pole)
    assert layer.value(grid.latitudes()[5100], grid.longitudes()[11520]) == pytest.approx(4.533233e-05, rel=1e-6)
    assert np.isnan(layer.value(grid.latitudes()[0], 0.0)) and np.isnan(layer.value(grid.latitudes()[-1], 0.0))
    assert np.isnan(layer.value(52.2, 0.1))  # Cambridge: existing arable, no change
    r = layer.read("all", bbox=BBox(-0.5, 51.9, 0.6, 52.5))
    assert r.data.shape == (36, 66)


@pytest.mark.skipif(not (REAL_DATA / "versions.json").exists(), reason="real catalogue not present")
def test_real_catalogue() -> None:
    cat = Catalogue(REAL_DATA)
    rel = cat.latest()
    assert rel.version == "1.01" and rel.path == "v1.01" and rel.doi == "10.5281/zenodo.14945383"
    store = cat.open("1.01")
    assert store.version == "1.01"
    assert store.attrs["zenodo_record"] == 14945383 and store.attrs["concept_doi"] == "10.5281/zenodo.14188449"


def _reachable(url: str) -> bool:
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "life-metric-tests"})  # the CDN rejects urllib's default agent
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


@contextmanager
def _remote_reads():
    """Skip unavailable HTTP transfers while keeping schema failures visible."""
    try:
        yield {"client_kwargs": {"timeout": aiohttp.ClientTimeout(total=20)}}
    except (aiohttp.ClientError, TimeoutError) as exc:
        pytest.skip(f"source.coop transfer unavailable: {type(exc).__name__}: {exc}")


@pytest.mark.skipif(not _reachable("https://data.source.coop/tessera/life/v1.01/zarr.json"), reason="source.coop not reachable")
def test_published_store() -> None:
    from life_metric import metadata, read, sample

    with _remote_reads() as options:
        assert metadata(storage_options=options)["version"] == "1.01"
        grid = Grid(21600, 10800, 1 / 60, -180.0, 90.0)
        value = sample("arable_0.25", [(grid.longitudes()[11520], grid.latitudes()[5100])],
                       storage_options=options)[0]
        assert value == pytest.approx(4.533233e-05, rel=1e-6)
        values, transform = read("arable_0.25", bounds=(-0.5, 51.9, 0.6, 52.5), level=4,
                                 storage_options=options)
        assert values.shape == (10, 17) and values.dtype == np.dtype("float32")
        assert transform.a == pytest.approx(4 / 60)


@pytest.mark.skipif(not _reachable("https://data.source.coop/tessera/life/v1.1~beta1/zarr.json"), reason="published beta not reachable")
def test_published_beta_store() -> None:
    from life_metric import metadata, read
    from rasterio.windows import Window as RioWindow

    with _remote_reads() as options:
        attrs = metadata(version="1.1~beta1", storage_options=options)
        assert attrs["version"] == "1.1~beta1"
        assert list(attrs["scenarios"]) == ["arable", "pasture", "urban", "restore", "restore_agriculture", "restore_all"]
        assert list(attrs["curves"]) == ["0.25"]
        assert "overview" in attrs["data_model"]["overviews"].lower()
        values, _ = read("restore_agriculture_0.25", version="1.1~beta1", window=RioWindow(11000, 5000, 1, 1),
                         storage_options=options)
        assert values.dtype == np.dtype("float64")
        with open_dataset(version="1.1~beta1", storage_options=options) as dataset:
            assert dataset["restore_all_area_changed"].isel(lat=5000, lon=11000).to_numpy().dtype == np.dtype("float64")
            assert dataset.rio.crs.to_epsg() == 4326
