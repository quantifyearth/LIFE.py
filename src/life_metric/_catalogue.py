"""Catalogues: ``versions.json`` manifests that list released stores."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import fsspec

MANIFEST = "versions.json"
DEFAULT_CATALOGUE = "https://data.source.coop/tessera/life"


def version_key(version: str) -> tuple[tuple[int, str], ...]:
    """Order numeric parts of release names numerically, including beta numbers."""
    return tuple((int(part), "") if part.isdigit() else (-1, part)
                 for part in re.findall(r"[0-9]+|[^0-9]+", version))


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://", "s3://", "gs://"))


def _join(base: str, path: str) -> str:
    if _is_url(base):
        return urljoin(base if base.endswith("/") else base + "/", path)
    return os.path.join(base, path)


def _read_json(location: str) -> Any:
    # fsspec is the filesystem layer zarr itself uses, so every location a
    # store can live at (directory, http, s3, gs, ...) is readable here too.
    with fsspec.open(location, "rb") as f:
        return json.load(f)


@dataclass(frozen=True)
class Release:
    """One released store listed in a catalogue."""

    version: str
    path: str
    url: str
    """The store location, resolved against the catalogue base."""
    released: str | None = None
    doi: str | None = None
    description: str | None = None


class Catalogue:
    """A set of released stores described by a ``versions.json`` manifest.

    The manifest lives directly under ``base``, which may be a directory or a
    URL, and maps version strings to relative store paths. With no argument
    the published catalogue on source.coop is used. Reading the manifest is
    deferred until a release is requested.
    """

    def __init__(self, base: str | os.PathLike[str] = DEFAULT_CATALOGUE) -> None:
        self.base = str(base)
        self._manifest: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._manifest is None:
            m = _read_json(_join(self.base, MANIFEST))
            if not isinstance(m, dict) or "versions" not in m:
                raise ValueError(f"{self.base}/{MANIFEST} is not a catalogue manifest")
            self._manifest = m
        return self._manifest

    def releases(self) -> list[Release]:
        """Return every release in version order."""
        m = self._load()
        out = []
        for version, info in m["versions"].items():
            out.append(Release(
                version=str(version), path=info["path"], url=_join(self.base, info["path"]),
                released=info.get("released"), doi=info.get("doi"), description=info.get("description"),
            ))
        return sorted(out, key=lambda r: version_key(r.version))

    def release(self, version: str) -> Release:
        """Return the release called ``version``; raise KeyError if absent."""
        for r in self.releases():
            if r.version == version:
                return r
        raise KeyError(f"version {version!r} is not in {self.base}; have {[r.version for r in self.releases()]}")

    def latest(self) -> Release:
        """Return the release the manifest marks as latest, else the highest version."""
        m = self._load()
        if "latest" in m:
            return self.release(str(m["latest"]))
        return self.releases()[-1]

    def open(self, version: str | None = None, **kwargs: Any) -> Any:
        """Open the store for ``version``, or the latest release when omitted.

        Keyword arguments are passed to :func:`life_metric.open_store`.
        """
        from ._store import open_store

        rel = self.latest() if version is None else self.release(version)
        return open_store(rel.url, **kwargs)
