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
