# 8. Blend taxa

Set `taxon=None` to read every score band into a NumPy stack. The first band
is `all`, followed by amphibians, birds, mammals, and reptiles. Omit `all`
from the blend and give each class its own colour range. The map shows the
strongest class and darkens places where classes are similarly affected.

```python
from life_metric import colour, read

values, _ = read("arable_0.25", bounds=(90, -12, 130, 25), taxon=None, level=4)
stack = values[1:]
blend = colour.make_blend([colour.percentile_abs(band, 99) for band in stack])
with open("taxa.png", "wb") as output:
    output.write(colour.to_png(blend.rgba(stack)))
```

Run the [script](taxa_blend.py) from the repository root.

```sh
uv run python examples/8-taxa-blend/taxa_blend.py /path/to/v1.01 --output taxa.png
```

Return to the [example index](../README.md).
