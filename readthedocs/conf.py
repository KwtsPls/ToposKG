# Configuration file for the Sphinx documentation builder.
# See: https://www.sphinx-doc.org/

project = "ToposKG"
author = "Konstantinos Plas"
copyright = "2026, Konstantinos Plas"

extensions = [
    "myst_parser",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_title = "ToposKG documentation"

# Keep this directory if you later want to add custom CSS or images.
html_static_path = ["_static"]
