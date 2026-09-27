"""Query a score and the area changed at one latitude-longitude point."""

import sys

from life_metric import open_store


def query(source: str | None, lat: float, lon: float) -> tuple[float, float]:
    """Print and return the arable score and changed area at a point."""
    store = open_store(source) if source else open_store()
    print(f"{store.info.title} (version {store.version})")
    print("Scenarios:", ", ".join(store.scenarios))
    print("Curves:", ", ".join(store.curves))
    score = store.layer("arable", "0.25").value(lat, lon)
    area = store.area("arable").value(lat, lon)
    print(f"Score: {score} extinctions per km² changed")
    print(f"Area changed: {area} m²")
    return score, area


if __name__ == "__main__":
    query(sys.argv[1] if len(sys.argv) > 1 else None,
          float(sys.argv[2]) if len(sys.argv) > 2 else -19.5,
          float(sys.argv[3]) if len(sys.argv) > 3 else 47.0)
