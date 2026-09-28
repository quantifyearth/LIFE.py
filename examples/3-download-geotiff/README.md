# 3. Download a GeoTIFF

`download()` saves a bounded GeoTIFF with the values, CRS, transform, units,
band labels, citation, and data terms. Open the file with rasterio and use
your usual workflow. Install `life-metric[geo]` for this step. The example
refuses to replace an existing output unless `--overwrite` is given.

```python
import rasterio
from life_metric import download

path = download("restore_0.25", "region.tif", bounds=(43, -26, 51, -12))
with rasterio.open(path) as dataset:
    values = dataset.read(1, masked=True)
    print(values.mean(), dataset.transform)
```

Run the [script](download_geotiff.py) from the repository root.

```sh
uv run --extra geo python examples/3-download-geotiff/download_geotiff.py /path/to/v1.01 --output region.tif
```

Next, [sample points](../4-sample-points/README.md).
