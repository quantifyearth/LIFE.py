"""Fetch the Zenodo archive with resume support, verify it, and unpack it."""

from __future__ import annotations

import hashlib
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from ..dataset import LAYERS, TERMS_PDF, ZIP_MD5, ZIP_NAME, ZIP_PREFIX, ZIP_SIZE, ZIP_URL

_CHUNK = 8 << 20


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def md5sum(path: Path) -> str:
    """Return the hexadecimal MD5 checksum of a local file."""
    h = hashlib.md5()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def download(
    raw_dir: Path,
    url: str = ZIP_URL,
    expected_size: int = ZIP_SIZE,
    expected_md5: str | None = ZIP_MD5,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Download the archive into *raw_dir*, resuming a partial file if present.

    Returns the path of the verified zip. Raises RuntimeError on a checksum
    mismatch so a corrupt archive never reaches the converter.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / ZIP_NAME
    have = dest.stat().st_size if dest.exists() else 0
    if on_progress is not None:
        on_progress(have, expected_size)

    if have > expected_size:
        raise RuntimeError(f"{dest} is larger ({have}) than the published size ({expected_size})")

    if have < expected_size:
        headers = {"Range": f"bytes={have}-"} if have else {}
        _log(f"downloading {url} -> {dest} (resuming at {have / 1e9:.2f} GB)" if have else f"downloading {url} -> {dest}")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp, dest.open("ab" if have else "wb") as out:
            if have and resp.status != 206:
                raise RuntimeError("server ignored the Range header; delete the partial file and retry")
            t0 = time.monotonic()
            done = have
            last = t0
            while chunk := resp.read(_CHUNK):
                out.write(chunk)
                done += len(chunk)
                if on_progress is not None:
                    on_progress(done, expected_size)
                now = time.monotonic()
                if on_progress is None and now - last > 5:
                    rate = (done - have) / (now - t0) / 1e6
                    _log(f"  {done / 1e9:6.2f} / {expected_size / 1e9:.2f} GB  ({rate:.1f} MB/s)")
                    last = now
        have = dest.stat().st_size
        if have != expected_size:
            raise RuntimeError(f"download ended at {have} bytes, expected {expected_size}; rerun to resume")

    if expected_md5:
        _log(f"verifying md5 of {dest}")
        got = md5sum(dest)
        if got != expected_md5:
            raise RuntimeError(f"md5 mismatch for {dest}: got {got}, expected {expected_md5}")
        _log("  md5 ok")
    return dest


def extract(zip_path: Path, raw_dir: Path, names: list[str] | None = None) -> list[Path]:
    """Unpack the layer GeoTIFFs (and the terms PDF) flat into *raw_dir*.

    Members already present with the right size are skipped, so this is safe
    to rerun. Returns the paths of all requested members.
    """
    wanted = names or [layer.source for layer in LAYERS] + [TERMS_PDF]
    out: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in wanted:
            info = zf.getinfo(ZIP_PREFIX + name)
            dest = raw_dir / name
            if dest.exists() and dest.stat().st_size == info.file_size:
                _log(f"  have {name}")
            else:
                _log(f"  extracting {name} ({info.file_size / 1e6:.0f} MB)")
                with zf.open(info) as src, dest.open("wb") as dst:
                    while chunk := src.read(_CHUNK):
                        dst.write(chunk)
            out.append(dest)
    return out
