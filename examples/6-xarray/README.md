# 6. Use xarray

`open_dataset()` returns a native xarray Dataset with named taxa, dataset
attributes, and CRS metadata for its `.rio` accessor. Use `.sel()` and NumPy
conversion as usual. Latitude coordinates decrease from north to south.
Install `life-metric[xarray]` for this step. Overview means are for exploration;
use level 1 for pixel totals.

```python
from life_metric import open_dataset

with open_dataset(level=4) as dataset:
    birds = dataset["arable_0.25"].sel(taxon="AVES")
    region = birds.sel(lon=slice(43, 51), lat=slice(-12, -26))
    print(region.to_numpy(), region.rio.crs)
```

Run the [script](xarray_example.py) from the repository root.

```sh
uv run --extra xarray python examples/6-xarray/xarray_example.py /path/to/v1.01
```

Next, [colour a map](../7-colour-map/README.md).
