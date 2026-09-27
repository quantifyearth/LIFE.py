"""Convert the unpublished v1.1 beta score and area GeoTIFFs to Zarr.

Run from the repository root: uv run --extra build examples/build_beta_store.py OUT \
    --scores /path/to/deltap_final --areas /path/to/habitat
The output directory must not already exist. Source TIFFs are only read.
"""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio

from life_metric import dataset as D
from life_metric.build import (Options, build_pyramid, convert_layers, create_pyramid,
                               create_store, finalize, verify_layers)
from life_metric.build.convert import root_attributes

VERSION = "1.1~beta1"
SCENARIOS = {
    "arable": "Conversion to arable land in the beta source.",
    "pasture": "Conversion to pasture in the beta source.",
    "urban": "Conversion to urban land in the beta source.",
    "restore": "Restoration to natural habitat in the beta source.",
    "restore_agriculture": "Restoration of agricultural land in the beta source.",
    "restore_all": "The broader restoration scenario labelled restore_all in the beta source.",
}
TAXA = {
    "all": "all terrestrial vertebrates",
    "AMPHIBIA": "amphibians",
    "AVES": "birds",
    "MAMMALIA": "mammals",
    "REPTILIA": "reptiles",
}


def layers() -> list[D.Layer]:
    """Describe each beta TIFF without borrowing v1.01-only scenarios."""
    result = []
    for scenario, meaning in SCENARIOS.items():
        result.append(D.Layer(
            name=f"{scenario}_0.25", scenario=scenario, kind="life", curve="0.25",
            source=f"scaled_{scenario}_0.25.tif", bands=D.TAXA, fill_value=float("nan"),
            long_name_override=f"LIFE score, {scenario} scenario, power-law curve z = 0.25",
            description_override=(
                "Change in expected extinctions over 100 years per km2 of land changed "
                f"within the pixel. {meaning} Positive values mean more extinctions; "
                "NaN means no land changes under this scenario."
            ),
        ))
        result.append(D.Layer(
            name=f"{scenario}_area_changed", scenario=scenario, kind="area", curve=None,
            source=f"{scenario}_diff_area.tif", bands=("area",), fill_value=0.0,
            long_name_override=f"area of land changed per pixel, {scenario} scenario",
            description_override=(
                f"Area in m2 of land changed within the pixel. {meaning} "
                "Zero means no land changes. Divide by 1e6 and multiply by the "
                "matching score to estimate the change in expected extinctions "
                "if all eligible land in the pixel changes."
            ),
        ))
    return result


def beta_attributes(opts: Options) -> dict:
    """Use the shared grid conventions with beta-specific provenance."""
    attrs = root_attributes(opts, None)
    for key in ("source_doi", "source_url", "zenodo_record", "concept_doi", "zenodo_records",
                "published_catalogue", "source_archive", "source_archive_md5", "pipeline", "creators"):
        attrs.pop(key, None)
    attrs.update({
        "title": f"LIFE: Land-cover change Impacts on Future Extinctions, {VERSION}",
        "summary": (
            "Unpublished beta global 1 arc-minute maps of expected extinctions "
            "per km2 of land changed, with six land-cover scenarios, the z = 0.25 "
            "persistence curve, and changed area per pixel."
        ),
        "version": VERSION,
        "release_status": "unpublished beta",
        "source_description": (
            "Six float64 score GeoTIFFs from deltap_final and six float64 "
            "changed-area GeoTIFFs from habitat, supplied as v1.1~beta1. "
            "No Zenodo record or DOI was supplied for this beta."
        ),
        "source_files": {s: {"score": f"scaled_{s}_0.25.tif", "area": f"{s}_diff_area.tif"} for s in SCENARIOS},
        "scenarios": SCENARIOS,
        "curves": {"0.25": D.CURVE_DESCRIPTION["0.25"]},
        "taxa": TAXA,
    })
    attrs["data_model"]["missing_data"] = (
        "Score NaN means no land changes under the scenario; area zero means no land changes."
    )
    return attrs


def check_source(path: Path, bands: tuple[str, ...]) -> None:
    """Require the beta's full-globe float64 WGS84 grid and expected bands."""
    with rasterio.open(path) as src:
        if (src.height, src.width, src.count) != (10800, 21600, len(bands)):
            raise ValueError(f"{path}: unexpected shape or band count")
        if src.crs != rasterio.crs.CRS.from_epsg(4326):
            raise ValueError(f"{path}: expected EPSG:4326")
        if not np.allclose(src.transform.to_gdal(), D.geotransform(), rtol=0, atol=1e-9):
            raise ValueError(f"{path}: unexpected geotransform")
        if any(dtype != "float64" for dtype in src.dtypes):
            raise ValueError(f"{path}: expected float64 data")
        if len(bands) > 1 and src.descriptions != bands:
            raise ValueError(f"{path}: unexpected band labels {src.descriptions}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="new v1.1~beta1 store directory")
    parser.add_argument("--scores", type=Path, required=True, help="directory with six scaled score TIFFs")
    parser.add_argument("--areas", type=Path, required=True, help="directory with six diff-area TIFFs")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"{args.out} already exists")

    which = layers()
    opts = Options(height=10800, width=21600, row_offset=0, dtype="float64",
                   taxa_descriptions=TAXA, workers=args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="life-beta-raw-") as tmp:
        raw = Path(tmp)
        for layer in which:
            source_dir = args.scores if layer.kind == "life" else args.areas
            source = source_dir / layer.source
            check_source(source, layer.bands)
            (raw / layer.source).symlink_to(source.resolve())
        create_store(args.out, opts, which, attributes=beta_attributes(opts))
        convert_layers(args.out, raw, which, opts)
        create_pyramid(args.out, opts, which)
        build_pyramid(args.out, which, workers=args.workers)
        finalize(args.out)
        results = verify_layers(args.out, raw, which, workers=args.workers, gdal=True)
        failed = [r.name for r in results if not r.ok]
        if failed:
            raise RuntimeError(f"source comparison failed for {failed}")
    print(f"built and verified {args.out} ({len(which)} layers)")


if __name__ == "__main__":
    main()
