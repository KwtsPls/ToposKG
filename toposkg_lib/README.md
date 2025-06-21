<div align="center">
  <h1>toposkg-lib</h1>
</div>

<div align="center">
  A Python library for Knowledge Graph customization and expansion.
</div>

## Overview
toposkg-lib is a Python library developed as part of the Topos framework. It provides easy access to powerful functionality for customizing and extending ToposKG but is also compatible with arbitrary source files.

## Highlights
- **Powerful features.** Customize and expand ToposKG using powerful tools for geospatial interlinking, toponym translation and entity linking.
- **Ease of use.** toposkg-lib is designed around a simple builder pattern, simplifying the process of generating your Knowledge Graph.
- **Natural Language Interface.** toposkg-lib can be used with a textual interface, powered by LLM function calling.
- **Active development.** toposkg-lib will keep getting updates as we work on our projects.

## Repository contents
- `examples/`: Additional data, used in examples.
- `notebooks/`: Jupyter Notebooks that showcase the functionality of the library.
- `toposkg/`: The source code. Some files contain `main` functions that also include examples of use.

## Getting Started

### pip

We recommend using toposkg-lib through [pip](https://pypi.org/project/toposkg/).

```sh
pip install toposkg
```

If you want to include the translation functionality.

```sh
pip install toposkg[tl]
```

If you want to include the function calling functionality.

```sh
pip install toposkg[fc]
```

We recommend that you install this custom version of RDF-lib before using toposkg-lib.

```sh
pip install git+https://github.com/SKefalidis/rdflib-speed@main
```

Otherwise you can use the original rdflib.

### Simple example

```python
from toposkg.toposkg_lib_core import KnowledgeGraphBlueprintBuilder, KnowledgeGraphSourcesManager

# Create a KnowledgeGraphSourcesManager object to load the available data sources and their metadata
sources_manager = KnowledgeGraphSourcesManager(['PATH_TO_YOUR_SOURCES'])

# See the available data sources
sources_manager.print_available_data_sources()

# Create a KnowledgeGraphBlueprintBuilder object to build the knowledge graph blueprint
builder = KnowledgeGraphBlueprintBuilder()

builder.set_name("ToposKG.nt")
builder.set_output_dir("/home/example/")

builder.add_source_path("PATH_TO_KG_SOURCE_1") # relative or absolute path
builder.add_source_path("PATH_TO_KG_SOURCE_2")

# Use the blueprint to construct the knowledge graph
blueprint = builder.build()
blueprint.construct()
```

### Advanced Examples

Explore advanced functionality with our interactive Google Colab notebooks:

- 🚀 **[Quickstart Notebook](https://colab.research.google.com/drive/1mv0YYDcd_zWzl1IC7jgxHERwdiHo6I-4?usp=sharing)**  

A fast introduction to the capabilities of toposkg-lib.

- 🤖 **[Chatbot Notebook](https://colab.research.google.com/drive/1A1F23tJUbGlIsLPEXaNi8lK9Y5zYOS0F?usp=sharing)**

Our LLM-based chatbot that utilizes toposkg-lib, in action.

