"""Write the ``versions.json`` catalogue that lists released stores."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import zarr

from .._catalogue import MANIFEST, version_key


def write_manifest(data_dir: Path, store: Path, *, released: str | None = None,
                   description: str | None = None, latest: str | None = None) -> dict[str, Any]:
    """Add *store* to ``<data_dir>/versions.json`` and return the manifest.

    The store's version and DOI come from its root attributes; its path is
    recorded relative to *data_dir*. ``latest`` defaults to the highest
    version listed.
    """
    root = zarr.open_group(store, mode="r")
    version = str(root.attrs.get("version", "unknown"))
    manifest_path = data_dir / MANIFEST
    manifest: dict[str, Any] = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"versions": {}}
    path = str(store.relative_to(data_dir)) if store.is_relative_to(data_dir) else str(store)
    entry = {"path": path, "doi": root.attrs.get("source_doi"), "released": released,
             "description": description or root.attrs.get("title")}
    manifest["versions"][version] = {k: v for k, v in entry.items() if v is not None}
    manifest["latest"] = latest or max(manifest["versions"], key=version_key)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
