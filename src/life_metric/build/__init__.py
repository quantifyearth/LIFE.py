"""Build a LIFE store from the published GeoTIFFs.

The pipeline is: :func:`download` the Zenodo archive and :func:`extract`
its GeoTIFFs, :func:`create_store` and :func:`convert_layers` to write the
base level, :func:`create_pyramid` and :func:`build_pyramid` to add the
overview levels, :func:`finalize` to consolidate metadata, and
:func:`verify_layers` to compare the result with the source cell for cell.
:func:`write_manifest` lists the store in a ``versions.json`` catalogue. The
``life-metric`` command runs each step. Reading and writing GeoTIFFs needs
the ``build`` extra, which installs rasterio.
"""

from .convert import Options, convert_layers, create_store, describe, finalize
from .download import download, extract, md5sum
from .manifest import write_manifest
from .pyramid import build_pyramid, create_pyramid, downsample2
from .verify import VerifyResult, verify_layers

__all__ = [
    "Options", "VerifyResult", "build_pyramid", "convert_layers", "create_pyramid", "create_store", "describe",
    "download", "downsample2", "extract", "finalize", "md5sum", "verify_layers", "write_manifest",
]
