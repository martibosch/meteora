"""Docs config."""

import os
import sys

import pkg_resources

project = "Meteora"
author = "Martí Bosch"

release = pkg_resources.get_distribution("meteora").version
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_parser",
    "nbsphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
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
exclude_patterns = ["_build", "**.ipynb_checkpoints"]

# do NOT execute notebooks
nbsphinx_execute = "never"


# no prompts in rendered notebooks
# https://github.com/microsoft/torchgeo/pull/783
html_static_path = ["_static"]
html_css_files = ["notebooks.css"]
