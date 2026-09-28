"""Exercise reader commands against a small, descriptive Zarr store."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import numpy as np
import rasterio

from life_metric.cli import main


def run_cli(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 0


def test_help_works_without_opening_a_store(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["--help"])
    help_text = capsys.readouterr().out
    assert "query" in help_text
    assert "admin" in help_text


def test_sample_json_uses_store_metadata(store_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["query", "22.5", "-112.5", str(store_path), "--scenario", "restore",
             "--curve", "gompertz", "--taxon", "AVES", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert result["version"] == "0.9"
    assert result["layer"] == "restore_gompertz"
    assert result["taxon"] == "AVES"
    assert result["units"] == "extinctions km-2"
    assert result["value"] < 0


def test_sample_missing_and_area_json(store_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["sample", "82.5", "-112.5", str(store_path), "--json"])
    assert json.loads(capsys.readouterr().out)["value"] is None
    run_cli(["sample", "22.5", "-112.5", str(store_path), "--area", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert result["units"] == "m2"
    assert result["taxon"] == "area"
    assert result["value"] > 0


def test_query_reports_available_scenarios(store_path: Path,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["query", "22.5", "-112.5", str(store_path), "--scenario", "unknown"])
    assert exit_info.value.code == 1
    assert "choose from arable, restore" in capsys.readouterr().err


def test_info_and_releases_json(store_path: Path, catalogue_dir: Path,
                                capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["info", str(store_path), "--json"])
    info = json.loads(capsys.readouterr().out)
    assert info["scenarios"]["restore"] == "reversion"
    assert info["levels"][1]["factor"] == 2
    run_cli(["releases", "--catalogue", str(catalogue_dir), "--json"])
    releases = json.loads(capsys.readouterr().out)
    assert releases["latest"] == "0.9"
    assert [entry["version"] for entry in releases["versions"]] == ["0.9", "0.10"]


@pytest.mark.parametrize(("step", "script", "extra", "expected"), [
    ("1-read-region", "read_region.py", ["--bounds", "-135", "15", "-105", "45"], "pixels"),
    ("2-mask-polygon", "mask_polygon.py", ["--bounds", "-135", "15", "-105", "45"], "Included pixels"),
    ("3-download-geotiff", "download_geotiff.py", ["--bounds", "-135", "15", "-105", "45"], "Saved"),
    ("4-sample-points", "sample_points.py", [], "convert"),
    ("6-xarray", "xarray_example.py", ["--bounds", "-135", "15", "-105", "45", "--level", "2"], "Region at level 2"),
    ("7-colour-map", "colour_map.py", ["--bounds", "-135", "15", "-105", "45"], "Wrote"),
    ("8-taxa-blend", "taxa_blend.py", ["--bounds", "-135", "15", "-105", "45", "--level", "2"], "wrote"),
])
def test_reader_examples_run_offline(store_path: Path, tmp_path: Path, step: str, script: str,
                                     extra: list[str], expected: str) -> None:
    example = Path(__file__).parents[1] / "examples" / step / script
    command = [sys.executable, str(example), str(store_path), *extra]
    if "colour" in step or "blend" in step:
        output = tmp_path / "map.png"
        command += ["--output", str(output)]
    if "geotiff" in step:
        output = tmp_path / "region.tif"
        command += ["--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert expected in result.stdout
    if "colour" in step or "blend" in step:
        assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    if "geotiff" in step:
        with rasterio.open(output) as dataset:
            assert dataset.crs.to_epsg() == 4326
            assert dataset.read(1).shape == (2, 2)


def test_version_example_runs_offline(catalogue_dir: Path) -> None:
    example = Path(__file__).parents[1] / "examples" / "5-choose-version" / "choose_version.py"
    result = subprocess.run([sys.executable, str(example), str(catalogue_dir), "--version", "0.9"],
                            capture_output=True, text=True, check=True)
    assert "Opened 0.9" in result.stdout
    assert "Scenarios: arable, restore" in result.stdout


def test_download_region_npz(store_path: Path, tmp_path: Path,
                             capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "region.npz"
    run_cli(["download", str(target), str(store_path), "--bbox", "-135", "15", "-105", "45",
             "--scenario", "restore", "--taxon", "AVES"])
    capsys.readouterr()
    with np.load(target, allow_pickle=False) as archive:
        assert archive["data"].shape == (2, 2)
        assert archive["data"][1, 1] < 0
        assert archive["lat"].tolist() == [37.5, 22.5]
        assert archive["lon"].tolist() == [-127.5, -112.5]
        metadata = json.loads(str(archive["metadata"]))
        assert metadata["bands"] == ["AVES"]
        assert metadata["units"] == "extinctions km-2"


def test_download_refuses_overwrite(store_path: Path, tmp_path: Path,
                                    capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "region.npz"
    target.write_bytes(b"existing")
    with pytest.raises(SystemExit) as exit_info:
        main(["download", str(target), str(store_path), "--bbox", "-135", "15", "-105", "45"])
    assert exit_info.value.code == 1
    assert target.read_bytes() == b"existing"
    assert "--overwrite" in capsys.readouterr().err


def test_documented_cli_example(store_path: Path, tmp_path: Path) -> None:
    package_root = Path(__file__).parents[1]
    script = package_root / "examples" / "cli.sh"
    output = tmp_path / "region.tif"
    env = dict(os.environ, PATH=f"{package_root / '.venv' / 'bin'}:{os.environ['PATH']}")
    result = subprocess.run(["sh", str(script), str(store_path), str(output)],
                            capture_output=True, text=True, check=True, env=env)
    assert json.loads(result.stdout.splitlines()[0])["layer"] == "arable_0.25"
    with rasterio.open(output) as dataset:
        assert dataset.read(1).size > 0
        assert dataset.tags()["terms_of_use"] == "Non-commercial use only. IBAT."
