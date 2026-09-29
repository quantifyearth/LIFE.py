# 5. Choose a version

`versions()` returns dictionaries for the releases in a catalogue.
`metadata()` reads the selected store's attributes without reading pixels.
Inspect its scenario and curve descriptions before selecting a layer.

```python
from life_metric import metadata, versions

print(versions())
attrs = metadata(version="1.01")
print(attrs["scenarios"], attrs["curves"])
```

Run the [script](choose_version.py) from the repository root.

```sh
uv run python examples/5-choose-version/choose_version.py /path/to/catalogue --version 1.01
```

Next, [use xarray](../6-xarray/README.md).
