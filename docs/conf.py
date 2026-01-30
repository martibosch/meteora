"""Docs config."""

import dataclasses
import os
import sys
from importlib import metadata

from sphinx.builders.latex import transforms
from sphinxcontrib.bibtex import plugin as sphinxcontrib_bibtex_plugin
from sphinxcontrib.bibtex.style.referencing import BracketStyle
from sphinxcontrib.bibtex.style.referencing.author_year import AuthorYearReferenceStyle

project = "Meteora"
author = "Martí Bosch"

release = metadata.version("meteora")
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_nb",
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
exclude_patterns = ["_build", "**.ipynb_checkpoints"]

# execute notebooks during the docs build
nb_execution_mode = "cache"
nb_execution_excludepatterns = [r".*/[aA]01-.*"]
# need high timeout for the why-meteora.ipynb notebook
nb_execution_timeout = 180
nb_kernel_rgx_aliases = {"^pixi-kernel-python3$": "python3"}


# citation styles
def bracket_style() -> BracketStyle:
    """Bracket style."""
    return BracketStyle(
        left="(",
        right=")",
    )


@dataclasses.dataclass
class MyReferenceStyle(AuthorYearReferenceStyle):
    """Custom reference style."""

    bracket_parenthetical: BracketStyle = dataclasses.field(
        default_factory=bracket_style
    )
    bracket_textual: BracketStyle = dataclasses.field(default_factory=bracket_style)
    bracket_author: BracketStyle = dataclasses.field(default_factory=bracket_style)
    bracket_label: BracketStyle = dataclasses.field(default_factory=bracket_style)
    bracket_year: BracketStyle = dataclasses.field(default_factory=bracket_style)


sphinxcontrib_bibtex_plugin.register_plugin(
    "sphinxcontrib.bibtex.style.referencing", "author_year_round", MyReferenceStyle
)


# work-around to get LaTeX references at the same place as HTML
# see https://github.com/mcmtroffaes/sphinxcontrib-bibtex/issues/156
class DummyTransform(transforms.BibliographyTransform):
    """Dummy transform."""

    def run(self, **kwargs):
        """Run."""
        pass


transforms.BibliographyTransform = DummyTransform

# bibliography
bibtex_bibfiles = ["user-guide/references.bib"]
bibtex_default_style = "plain"
bibtex_reference_style = "author_year_round"


# no prompts in rendered notebooks
# https://github.com/microsoft/torchgeo/pull/783
html_static_path = ["_static"]
html_css_files = ["notebooks.css"]
