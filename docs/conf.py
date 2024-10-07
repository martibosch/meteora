"""Docs config."""

import os
import sys

project = "Meteora"
author = "Martí Bosch"

__version__ = "0.1.0"
version = __version__
release = __version__

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "myst_parser", "nbsphinx"]

autodoc_typehints = "description"
html_theme = "pydata_sphinx_theme"

# https://myst-parser.readthedocs.io/en/stable/syntax/optional.html#auto-generated-header-anchors
myst_heading_anchors = 3

# add module to path
sys.path.insert(0, os.path.abspath(".."))

# exclude patterns from sphinx-build
exclude_patterns = ["_build", "**.ipynb_checkpoints"]
