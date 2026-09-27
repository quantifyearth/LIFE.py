# 8. Use xarray

Install the `xarray` extra to open a resolution level lazily as a Dataset.
The `taxon` coordinate carries species group names. Overview values are
averages for display and exploration; use level 1 for pixel totals.

```python
from life_metric import open_store

dataset = open_store().to_xarray(level=4)
birds = dataset["arable_0.25"].sel(taxon="AVES")
print(birds.dims)
```

Run the [script](xarray_levels.py) to average a bounded region. It requires
`life-metric[xarray]`.

```sh
uv run --extra xarray python examples/8-xarray-levels/xarray_levels.py /path/to/v1.01
```

Return to the [example index](../README.md).
