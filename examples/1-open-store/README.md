# 1. Open a store

Start by inspecting the store before choosing a layer. `Store.describe()`
prints the dataset title, scenarios, curves, taxa, resolution levels, and
layers from the Zarr metadata. It does not read any raster pixels.

```python
from life_metric import open_store

store = open_store()
print(store.describe())
```

Run the [script](open_store.py) from the repository root. Pass a local store
path to avoid the published URL.

```sh
uv run python examples/1-open-store/open_store.py /path/to/v1.01
```

Next, [query one point](../2-query-point/README.md).
