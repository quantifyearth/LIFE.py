"""List released versions and inspect one version's metadata."""

import argparse

from life_metric import DEFAULT_CATALOGUE, metadata, versions

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("catalogue", nargs="?", default=DEFAULT_CATALOGUE, help="catalogue directory or URL")
parser.add_argument("--version", help="release to inspect; default: catalogue latest")
args = parser.parse_args()

releases = versions(args.catalogue)
for release in releases:
    print(release["version"], release["url"])
version = args.version or next(release["version"] for release in releases if release["latest"])
attrs = metadata(version=version, catalogue=args.catalogue)
print("Opened", attrs["version"])
print("Scenarios:", ", ".join(attrs["scenarios"]))
print("Curves:", ", ".join(attrs["curves"]))
