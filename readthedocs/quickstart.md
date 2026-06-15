# Quickstart

The following is an abstract, but simple, example on how to leverage the high quality data sources available as RDF data through *ToposKG* to make your own, Geospatial Knowledge Graph. Instead of being forced to download and use the entirety of the graph, users can easily pick-n-choose the parts that are required for their use cases.

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
