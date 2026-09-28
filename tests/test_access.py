"""Compare the public API with standard rasterio and xarray workflows."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
import rasterio.mask
import xarray as xr
import zarr
from affine import Affine
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from rasterio.windows import Window
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape

import life_metric as life
from tests.conftest import H, RES, W, band_values


@pytest.fixture
def raster_source():
    with MemoryFile() as memory:
        with memory.open(driver="GTiff", width=W, height=H, count=5, dtype="float32",
                         crs="EPSG:4326", transform=from_origin(-180, 90, RES, RES), nodata=np.nan) as destination:
            destination.write(np.stack([band_values(band, 1.0) for band in range(5)]))
        with memory.open() as source:
            yield source


def test_numpy_bounds_and_rasterio_window(store_path: Path, raster_source) -> None:
    bounds = (-90, 0, 0, 45)
    window = Window(6, 3, 6, 3)
    expected = raster_source.read(3, window=window)
    values, transform = life.read("arable_0.25", source=store_path, taxon="AVES", bounds=bounds)
    assert isinstance(values, np.ndarray) and not isinstance(values, np.ma.MaskedArray)
    assert isinstance(transform, Affine)
    assert values.dtype == expected.dtype
    np.testing.assert_array_equal(values, expected)
    assert transform == raster_source.window_transform(window)
    selected, selected_transform = life.read("arable_0.25", source=store_path, taxon="AVES", window=window)
    np.testing.assert_array_equal(selected, values)
    assert selected_transform == transform
    stack, _ = life.read("arable_0.25", source=store_path, taxon=None, window=window)
    np.testing.assert_array_equal(stack, raster_source.read(window=window))


@pytest.mark.parametrize("all_touched", [False, True])
@pytest.mark.parametrize("form", ["shapely", "geojson", "features", "sequence", "multipolygon"])
def test_polygon_masks_match_rasterio(store_path: Path, raster_source, all_touched: bool, form: str) -> None:
    polygon = Polygon([(-131, 8), (-67, 8), (-67, 69), (-131, 69)],
                      holes=[[(-115, 31), (-115, 48), (-92, 48), (-92, 31)]])
    geometry = {
        "shapely": polygon,
        "geojson": mapping(polygon),
        "features": {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": mapping(polygon), "properties": {}}]},
        "sequence": [polygon],
        "multipolygon": MultiPolygon([polygon]),
    }[form]
    expected, expected_transform = rasterio.mask.mask(raster_source, [polygon], indexes=3,
                                                      crop=True, filled=False, all_touched=all_touched)
    values, transform = life.read("arable_0.25", source=store_path, taxon="AVES",
                                  geometry=geometry, all_touched=all_touched)
    assert isinstance(values, np.ma.MaskedArray)
    np.testing.assert_array_equal(values.data, expected.data)
    np.testing.assert_array_equal(values.mask, expected.mask)
    assert transform == expected_transform
    assert values.count() == expected.count()


def test_geometry_crs_and_missing_values(store_path: Path, raster_source) -> None:
    polygon = box(-129, 56, -89, 88)
    projected = shape(transform_geom("EPSG:4326", "EPSG:3857", mapping(polygon)))
    values, transform = life.read("arable_0.25", source=store_path, geometry=projected, crs="EPSG:3857")
    expected, expected_transform = rasterio.mask.mask(raster_source, [polygon], indexes=1, crop=True, filled=False)
    np.testing.assert_array_equal(values.mask, expected.mask)
    np.testing.assert_array_equal(values.data, expected.data)
    assert transform == expected_transform
    stack, _ = life.read("arable_0.25", source=store_path, geometry=polygon, taxon=None)
    expected_stack, _ = rasterio.mask.mask(raster_source, [polygon], crop=True, filled=False)
    np.testing.assert_array_equal(stack.mask, expected_stack.mask)
    np.testing.assert_array_equal(stack.data, expected_stack.data)


def test_masked_numpy_and_valid_zero_area(store_path: Path) -> None:
    values, _ = life.read("arable_0.25", source=store_path, bounds=(-180, 0, -90, 90), masked=True)
    assert isinstance(values, np.ma.MaskedArray)
    assert values.mask[0].all()
    assert not values.mask[3, 3] and values[3, 3] == 0
    area, _ = life.read("arable_area_changed", source=store_path, geometry=box(-180, 0, -90, 90))
    assert area[0, 0] == 0 and not area.mask[0, 0]


def test_longitude_latitude_samples(store_path: Path, raster_source) -> None:
    xy = [(-112.5, 22.5), (10, 30), (10, 91)]
    values = life.sample("arable_0.25", xy, source=store_path, taxon="AVES")
    expected = np.array([value[0] for value in raster_source.sample(xy, indexes=3)])
    np.testing.assert_array_equal(values, expected)
    assert values.dtype == np.dtype("float32")
    assert life.sample("arable_0.25", np.empty((0, 2)), source=store_path).shape == (0,)
    with pytest.raises(ValueError, match="shape"):
        life.sample("arable_0.25", [10, 30], source=store_path)
    with pytest.raises(ValueError, match="finite"):
        life.sample("arable_0.25", [(np.nan, 30)], source=store_path)


def test_native_xarray_and_rio(store_path: Path, tmp_path: Path, raster_source) -> None:
    dataset = life.open_dataset(store_path)
    assert isinstance(dataset, xr.Dataset)
    assert dataset.attrs["version"] == "0.9"
    assert dataset.attrs["terms_of_reference"] == "Non-commercial use only. IBAT."
    assert dataset.rio.crs == raster_source.crs
    assert dataset.rio.transform() == raster_source.transform
    assert list(dataset.taxon.values) == ["all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA"]
    birds = dataset["arable_0.25"].sel(taxon="AVES")
    assert birds.dtype == np.dtype("float32")
    assert birds.attrs["units"] == "extinctions km-2"
    assert np.isnan(birds.rio.nodata)
    assert dataset["arable_area_changed"].rio.nodata is None
    assert dataset["arable_area_changed"].isel(lat=0, lon=0).item() == 0
    region = birds.sel(lat=slice(45, 0), lon=slice(-90, 0))
    np.testing.assert_array_equal(region.to_numpy(), raster_source.read(3, window=Window(6, 3, 6, 3)))
    polygon = Polygon([(-131, 8), (-67, 8), (-67, 69), (-131, 69)])
    clipped = birds.rio.clip([polygon], crs="EPSG:4326", drop=False)
    expected, transform = rasterio.mask.mask(raster_source, [polygon], indexes=3, crop=False)
    np.testing.assert_array_equal(clipped.to_numpy(), expected)
    assert clipped.rio.transform() == transform
    path = tmp_path / "xarray.tif"
    region.rio.to_raster(path)
    with rasterio.open(path) as exported:
        np.testing.assert_array_equal(exported.read(1), region.to_numpy())
        assert exported.transform == raster_source.window_transform(Window(6, 3, 6, 3))
        assert exported.tags()["terms_of_use"] == "Non-commercial use only. IBAT."
    overview = life.open_dataset(store_path, level=2)
    assert overview.attrs["resolution_factor"] == 2
    assert overview.rio.transform().a == RES * 2
    assert overview.attrs["spatial:shape"] == [H // 2, W // 2]
    assert overview.attrs["spatial:transform"] == [RES * 2, 0, -180, 0, -RES * 2, 90]
    dataset.close()
    overview.close()


def test_geotiff_preserves_values_and_metadata(store_path: Path, tmp_path: Path, raster_source) -> None:
    path = life.download("arable_0.25", tmp_path / "scores.tif", source=store_path,
                         bounds=(-90, 0, 0, 45), taxon=None)
    with rasterio.open(path) as actual:
        np.testing.assert_array_equal(actual.read(), raster_source.read(window=Window(6, 3, 6, 3)))
        assert actual.transform == raster_source.window_transform(Window(6, 3, 6, 3))
        assert actual.crs == raster_source.crs
        assert actual.descriptions == ("all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA")
        assert actual.units == ("extinctions km-2",) * 5
        assert actual.compression == rasterio.enums.Compression.deflate
        assert np.isnan(actual.nodata)
        assert actual.tags()["citation"] == "Test citation."
        assert actual.tags()["terms_of_use"] == "Non-commercial use only. IBAT."
    with pytest.raises(FileExistsError):
        life.download("arable_0.25", path, source=store_path, bounds=(-90, 0, 0, 45))
    life.download("arable_0.25", path, source=store_path, bounds=(-90, 0, 0, 45), overwrite=True)
    with rasterio.open(path) as actual:
        assert actual.count == 1
    area_path = life.download("arable_area_changed", tmp_path / "area.tif", source=store_path,
                              bounds=(-180, 60, -90, 90))
    with rasterio.open(area_path) as actual:
        assert actual.nodata is None
        assert not actual.read(1, masked=True).mask.any()
        assert actual.read(1)[0, 0] == 0


def test_beta_float64_read_and_export(tmp_path: Path) -> None:
    root = zarr.create_group(tmp_path / "beta", zarr_format=3)
    root.attrs.update({"version": "1.1~beta1", "scenarios": {"restore_all": "restoration"},
                       "curves": {"0.25": "main"}, "taxa": {"all": "all species"},
                       "multiscales": {"layout": [{"asset": "0", "spatial:transform": [90, 0, -180, 0, -90, 90],
                                                    "spatial:shape": [2, 4]}]}})
    group = root.create_group("0")
    data = np.array([[[0.123456789012345, np.nan, 0, 1], [2, 3, 4, 5]]], dtype="float64")
    array = group.create_array("restore_all_0.25", data=data, dimension_names=("taxon", "lat", "lon"), fill_value=np.nan)
    array.attrs.update({"taxon_labels": ["all"], "units": "extinctions km-2"})
    values, _ = life.read("restore_all_0.25", source=root, bounds=(-180, -90, 180, 90))
    assert values.dtype == np.dtype("float64")
    np.testing.assert_array_equal(values, data[0])
    path = life.download("restore_all_0.25", tmp_path / "beta.tif", source=root, bounds=(-180, -90, 180, 90))
    with rasterio.open(path) as actual:
        assert actual.dtypes == ("float64",)
        np.testing.assert_array_equal(actual.read(1), data[0])


def test_metadata_version_selection_and_validation(store_path: Path, catalogue_dir: Path) -> None:
    assert life.metadata(store_path)["version"] == "0.9"
    assert [entry["version"] for entry in life.versions(catalogue_dir)] == ["0.9", "0.10"]
    assert [entry["latest"] for entry in life.versions(catalogue_dir)] == [True, False]
    values, _ = life.read("arable_0.25", version="0.9", catalogue=catalogue_dir, bounds=(-90, 0, 0, 45))
    assert values.shape == (3, 6)
    assert life.open_dataset(version="0.9", catalogue=catalogue_dir).attrs["version"] == "0.9"
    with pytest.raises(ValueError, match="source or version"):
        life.metadata(store_path, version="0.9")
    with pytest.raises(ValueError, match="exactly one"):
        life.read("arable_0.25", source=store_path)
    with pytest.raises(ValueError, match="exactly one"):
        life.read("arable_0.25", source=store_path, bounds=(-90, 0, 0, 45), geometry=box(-90, 0, 0, 45))
    with pytest.raises(ValueError, match="integer pixels"):
        life.read("arable_0.25", source=store_path, window=Window(0.5, 0, 2, 2))
    with pytest.raises(ValueError, match="overlap"):
        life.read("arable_0.25", source=store_path, window=Window(100, 0, 2, 2))
    with pytest.raises(ValueError, match="non-empty"):
        life.read("arable_0.25", source=store_path, geometry=Polygon())
