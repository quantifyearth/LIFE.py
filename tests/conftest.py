import json
from pathlib import Path

import numpy as np
import pytest
import zarr

W, H, RES = 24, 12, 15.0  # base grid: the whole globe in 15-degree pixels
TAXA = ("all", "AMPHIBIA", "AVES", "MAMMALIA", "REPTILIA")


def band_values(band: int, sign: float) -> np.ndarray:
    v = sign * (band + 1) * (np.arange(H * W, dtype="float32").reshape(H, W) + 1) * 1e-6
    v[0, :] = np.nan  # a NaN row
    v[3, 3] = 0.0
    return v


def downsample2(a: np.ndarray) -> np.ndarray:
    h, w = a.shape
    fin = np.isfinite(a)
    s = np.where(fin, a, 0).reshape(h // 2, 2, w // 2, 2).sum(axis=(1, 3), dtype="float64")
    c = fin.reshape(h // 2, 2, w // 2, 2).sum(axis=(1, 3))
    out = (s / np.maximum(c, 1)).astype("float32")
    out[c == 0] = np.nan
    return out


def level_entry(asset: str, factor: int, derived: str | None) -> dict:
    res = RES * factor
    e: dict = {"asset": asset, "transform": {"scale": [2.0, 2.0] if derived else [1.0, 1.0], "translation": [0.0, 0.0]},
               "spatial:transform": [res, 0.0, -180.0, 0.0, -res, 90.0], "spatial:shape": [H // factor, W // factor]}
    if derived:
        e["derived_from"] = derived
        e["resampling_method"] = "average"
    return e


@pytest.fixture(scope="session")
def store_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("cat") / "v0.9" / "life.zarr"
    root = zarr.create_group(path, zarr_format=3)
    root.attrs.update({
        "version": "0.9",
        "scenarios": {"arable": "conversion", "restore": "reversion"},
        "curves": {"0.25": "main", "gompertz": "gompertz"},
        "taxa": {t: t for t in TAXA},
        "multiscales": {"layout": [level_entry("0", 1, None), level_entry("1", 2, "0")], "resampling_method": "average"},
    })
    for asset, factor in (("0", 1), ("1", 2)):
        g = root.create_group(asset)
        rows, cols = H // factor, W // factor
        g.attrs.update({"factor": factor, "spatial:transform": [RES * factor, 0.0, -180.0, 0.0, -RES * factor, 90.0]})
        g.create_array("lat", data=90 - (np.arange(rows) + 0.5) * RES * factor, dimension_names=("lat",))
        g.create_array("lon", data=-180 + (np.arange(cols) + 0.5) * RES * factor, dimension_names=("lon",))
        g.create_array("taxon", data=np.arange(5, dtype="int8"), dimension_names=("taxon",))
        for scenario, sign in (("arable", 1.0), ("restore", -1.0)):
            for curve in ("0.25", "gompertz"):
                data = np.stack([band_values(b, sign) for b in range(5)])
                if factor > 1:
                    data = np.stack([downsample2(b) for b in data])
                a = g.create_array(f"{scenario}_{curve}", shape=data.shape, chunks=(1, 4, 4), dtype="float32",
                                   fill_value=np.nan, dimension_names=("taxon", "lat", "lon"))
                a[:] = data
                a.attrs.update({"units": "extinctions km-2", "long_name": f"{scenario} {curve}", "curve": curve,
                                "scenario": scenario, "kind": "life", "taxon_labels": list(TAXA), "source_bands": list(TAXA)})
            area = np.abs(band_values(0, 1.0)) * 1e9
            area[np.isnan(area)] = 0
            if factor > 1:
                area = downsample2(area)
            b = g.create_array(f"{scenario}_area_changed", shape=area.shape, chunks=(4, 4), dtype="float32",
                               fill_value=0.0, dimension_names=("lat", "lon"))
            b[:] = area
            b.attrs.update({"units": "m2", "kind": "area", "scenario": scenario})
    zarr.consolidate_metadata(path)
    return path


@pytest.fixture(scope="session")
def catalogue_dir(store_path: Path) -> Path:
    base = store_path.parent.parent
    (base / "versions.json").write_text(json.dumps({
        "latest": "0.9",
        "versions": {
            "0.9": {"path": "v0.9/life.zarr", "released": "2026-01-01", "doi": "10.5281/zenodo.0"},
            "0.10": {"path": "v0.10/life.zarr", "released": "2026-06-01"},
        },
    }))
    return base
