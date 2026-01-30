"""Docs config."""

import os
import sys
from importlib import metadata

project = "Meteora"
author = "Martí Bosch"

release = metadata.version("meteora")
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_parser",
    "nbsphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinxcontrib.bibtex",
    "sphinxemoji.sphinxemoji",
]

autodoc_typehints = "description"
html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "github_url": "https://github.com/martibosch/meteora",
}

# https://myst-parser.readthedocs.io/en/stable/syntax/optional.html#auto-generated-header-anchors
myst_heading_anchors = 3

# add module to path
sys.path.insert(0, os.path.abspath(".."))

# exclude patterns from sphinx-build
exclude_patterns = [
    "_build",
    "**.ipynb_checkpoints",
    "user-guide/a01-era5-download.ipynb",
]

# execute notebooks during the docs build
nbsphinx_execute = "always"
nbsphinx_kernel_name = "python3"

# bibliography
bibtex_bibfiles = ["user-guide/references.bib"]
bibtex_default_style = "unsrt"


# no prompts in rendered notebooks
# https://github.com/microsoft/torchgeo/pull/783
html_static_path = ["_static"]
html_css_files = ["notebooks.css"]
