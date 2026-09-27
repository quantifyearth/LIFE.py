"""Round-trip small synthetic GeoTIFFs through the build pipeline."""

from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
import zarr  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

from life_metric import dataset as L
from life_metric.build.convert import Options, convert_layers, create_store, finalize
from life_metric.build.verify import verify_layers

H, W = 70, 130  # deliberately not multiples of the chunk
GDAL_ZARR = tuple(map(int, rasterio.__gdal_version__.split(".")[:2])) >= (3, 12)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    rng = np.random.default_rng(0)
    transform = from_origin(float(L.LON_MIN), float(L.LAT_MAX), float(L.RES), float(L.RES))
    for layer in L.LAYERS:
        nb = len(layer.bands)
        data = rng.normal(size=(nb, H, W)).astype("float32") * 1e-8
        data[:, :40, :] = np.nan            # covers the whole first 32-row chunk row, must be skipped
        data[:, 30:35, 40:45] = 0.0
        with rasterio.open(
            raw / layer.source, "w", driver="GTiff", height=H, width=W, count=nb,
            dtype="float32", crs=f"EPSG:{L.EPSG}", transform=transform, nodata=np.nan,
            compress="lzw",
        ) as dst:
            dst.write(data)
            for i, b in enumerate(layer.bands, start=1):
                dst.set_band_description(i, b)
    return raw


def test_roundtrip(raw_dir: Path, tmp_path: Path) -> None:
    store = tmp_path / "life.zarr"
    opts = Options(chunk=32, workers=2, height=H, width=W)
    create_store(store, opts, overwrite=True)
    reports = convert_layers(store, raw_dir, list(L.LAYERS), opts)
    finalize(store)

    assert {r.name for r in reports} == {l.name for l in L.LAYERS}
    root = zarr.open_group(store, mode="r")
    layout = root.attrs["multiscales"]["layout"]
    assert [e["asset"] for e in layout] == ["0"] and layout[0]["spatial:shape"] == [H + 2, W]
    assert root.attrs["zarr_conventions"][0]["name"] == "multiscales"
    assert root.attrs["proj:wkt2"].startswith("GEOGCRS[")
    model = root.attrs["data_model"]
    assert "score * area_changed / 1e6" in model["pixel_total"]
    assert "not totals" in model["overviews"]
    from life_metric import open_store
    assert open_store(store).data_model == model
    a = root["0/arable_0.25"]
    assert a.shape == (5, H + 2, W) and a.chunks == (1, 32, 32)
    assert a.attrs["taxon_labels"] == list(L.TAXA) and a.attrs["spatial:dimensions"] == ["lat", "lon"]
    assert a.attrs["kind"] == "score"
    assert a.attrs["related_area_layer"] == "arable_area_changed"
    assert "all band" in a.attrs["band_relation"]
    # the first chunk row (polar fill row plus 31 NaN source rows) must not have been written
    assert a.nchunks_initialized < a.nchunks
    assert root["0/arable_area_changed"].shape == (H + 2, W)
    assert root["0/arable_area_changed"].attrs["kind"] == "area"
    assert root["0/lat"].shape == (H + 2,) and root["0/lon"].shape == (W,)
    assert root["0/lat"][0] == pytest.approx(90 - 1 / 120)
    assert root["0/taxon"].attrs["flag_meanings"] == " ".join(L.TAXA)
    assert root["0"].attrs["spatial:transform"] == [1 / 60, 0.0, -180.0, 0.0, -1 / 60, 90.0]
    # source row r is store row r + 1
    with rasterio.open(raw_dir / "scaled_arable_0.25.tif") as src:
        expect = src.read(3)
    assert np.array_equal(a[2, 1:-1, :], expect, equal_nan=True)
    assert np.isnan(a[2, 0, :]).all() and np.isnan(a[2, -1, :]).all()

    results = verify_layers(store, raw_dir, list(L.LAYERS), workers=2, rows=32, gdal=GDAL_ZARR)
    assert all(r.ok for r in results), [r for r in results if not r.ok]


def test_xarray_open(raw_dir: Path, tmp_path: Path) -> None:
    xr = pytest.importorskip("xarray")
    from life_metric import open_store

    store = tmp_path / "life.zarr"
    opts = Options(chunk=32, workers=2, height=H, width=W)
    create_store(store, opts, which=[L.layer_by_name("restore_gompertz")], overwrite=True)
    convert_layers(store, raw_dir, [L.layer_by_name("restore_gompertz")], opts)
    finalize(store)

    ds = open_store(store).to_xarray()
    assert list(ds["taxon"].values) == list(L.TAXA)
    with rasterio.open(raw_dir / "scaled_restore_gompertz.tif") as src:
        expect = src.read(3)
    got = ds["restore_gompertz"].sel(taxon="AVES").values
    assert got.shape == (H + 2, W)
    assert np.array_equal(got[1:-1], expect, equal_nan=True)
    assert ds["lat"].values[0] == pytest.approx(float(L.LAT_TOP - L.RES / 2))


def test_pyramid(raw_dir: Path, tmp_path: Path) -> None:
    from life_metric.dataset import level_shape
    from life_metric.build.pyramid import build_pyramid, create_pyramid, downsample2

    store = tmp_path / "life.zarr"
    opts = Options(chunk=32, workers=2, height=H, width=W)
    which = [L.layer_by_name("arable_0.25"), L.layer_by_name("restore_area_changed")]
    create_store(store, opts, which=which, overwrite=True)
    convert_layers(store, raw_dir, which, opts)
    create_pyramid(store, opts, which, factors=(2, 4), chunk=16)
    build_pyramid(store, which, factors=(2, 4), workers=2)
    finalize(store)

    root = zarr.open_group(store, mode="r")
    lvl2 = root["1/arable_0.25"]
    assert lvl2.shape == (5,) + level_shape(2, H + 2, W) == (5, 36, 65)
    assert root["2/arable_0.25"].shape == (5, 18, 33)
    assert root["1/lat"][0] == pytest.approx(90 - 1 / 60)
    assert root["2/restore_area_changed"].shape == (18, 33)
    assert "not the total changed area" in root["2/restore_area_changed"].attrs["resampling"]
    layout = root.attrs["multiscales"]["layout"]
    assert [e["asset"] for e in layout] == ["0", "1", "2"]
    assert layout[1]["derived_from"] == "0" and layout[1]["transform"] == {"scale": [2.0, 2.0], "translation": [0.0, 0.0]}
    assert layout[2]["derived_from"] == "1" and layout[2]["spatial:shape"] == [18, 33]
    assert layout[1]["spatial:transform"][0] == pytest.approx(2 / 60) and layout[1]["spatial:transform"][5] == 90.0
    assert root.attrs["multiscales"]["resampling_method"] == "average"
    assert root["1"].attrs["proj:code"] == "EPSG:4326"

    with rasterio.open(raw_dir / "scaled_arable_0.25.tif") as src:
        band = np.pad(src.read(2), ((1, 1), (0, 0)), constant_values=np.nan)  # the store's padded base
    expect2 = downsample2(band)
    assert np.array_equal(lvl2[1], expect2, equal_nan=True)
    assert np.array_equal(root["2/arable_0.25"][1], downsample2(expect2), equal_nan=True)
    # a 2x2 block with one finite value averages to that value, not NaN/4
    block = np.array([[1.0, np.nan], [np.nan, np.nan]], dtype="float32")
    assert downsample2(block)[0, 0] == 1.0
    assert np.isnan(downsample2(np.full((2, 2), np.nan, dtype="float32"))[0, 0])


def test_full_globe_float64_source(tmp_path: Path) -> None:
    from life_metric.build.pyramid import build_pyramid, create_pyramid

    raw = tmp_path / "raw"
    raw.mkdir()
    score, area = L.layer_by_name("arable_0.25"), L.layer_by_name("arable_area_changed")
    transform = from_origin(float(L.LON_MIN), float(L.LAT_TOP), float(L.RES), float(L.RES))
    values = np.arange(H * W, dtype="float64").reshape(H, W) / 1e9
    stack = np.stack([values * (i + 1) for i in range(5)])
    stack[:, :2] = np.nan
    for layer, data in ((score, stack), (area, values[None, ...])):
        with rasterio.open(raw / layer.source, "w", driver="GTiff", height=H, width=W,
                           count=len(layer.bands), dtype="float64", crs="EPSG:4326",
                           transform=transform) as dst:
            dst.write(data)

    opts = Options(chunk=32, workers=2, height=H, width=W, row_offset=0, dtype="float64")
    store = tmp_path / "v1.1~beta1"
    create_store(store, opts, [score, area])
    convert_layers(store, raw, [score, area], opts)
    create_pyramid(store, opts, [score, area], factors=(2,), chunk=16)
    build_pyramid(store, [score, area], factors=(2,), workers=2)
    finalize(store)

    root = zarr.open_group(store, mode="r")
    assert root.attrs["grid"]["row_offset"] == 0
    assert root["0/arable_0.25"].dtype == np.dtype("float64")
    assert root["0/arable_0.25"].shape == (5, H, W)
    assert np.array_equal(root["0/arable_0.25"][:], stack, equal_nan=True)
    assert root["1/arable_0.25"].dtype == np.dtype("float64")
    assert all(r.ok for r in verify_layers(store, raw, [score, area], workers=2, rows=32, gdal=GDAL_ZARR))
