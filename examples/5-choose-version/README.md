# 5. Choose a version

A catalogue lists released stores in `versions.json`. Its `latest` marker
selects the default release, while `Catalogue.open(version)` opens a named
one. Read the opened store's scenarios and curves before choosing a layer;
the v1.1 beta differs from v1.01.

```python
from life_metric import Catalogue

catalogue = Catalogue()
print([release.version for release in catalogue.releases()])
store = catalogue.open("1.1~beta1")
print(store.scenarios, store.curves)
```

Run the [script](choose_version.py) with a local catalogue directory or the
published catalogue. Omit `--version` to open the catalogue's latest release.

```sh
uv run python examples/5-choose-version/choose_version.py /path/to/catalogue --version 1.1~beta1
```

Next, [colour a map](../6-colour-map/README.md).
