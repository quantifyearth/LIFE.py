"""List the catalogue's releases and open one by version."""

import argparse

from life_metric import Catalogue

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("catalogue", nargs="?", help="catalogue directory or URL; default: published catalogue")
parser.add_argument("--version", help="release to open; default: catalogue latest")
args = parser.parse_args()

catalogue = Catalogue(args.catalogue) if args.catalogue else Catalogue()
for release in catalogue.releases():
    print(release.version, release.url)

store = catalogue.open(args.version)
print("Opened", store.version)
print("Scenarios:", ", ".join(store.scenarios))
print("Curves:", ", ".join(store.curves))
