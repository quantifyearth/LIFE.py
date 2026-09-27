"""Sphinx configuration for the Python package documentation."""

from life_metric import __version__

project = "LIFE.py"
copyright = "2026, life-metric contributors"
release = __version__
extensions = ["sphinx.ext.autodoc"]
autodoc_typehints = "none"
html_theme = "sphinx_rtd_theme"
