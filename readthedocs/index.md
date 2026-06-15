# ToposKG documentation

**ToposKG** A modular geospatial knowledge graph and toolkit designed for modern geospatial applications.

This documentation focuses on the toposkg-lib python library, its core functionalities, configuration parameters, and RDF generation workflow.

```{toctree}
:maxdepth: 2
:caption: Contents

installation
quickstart
toposkg-core
rdf-generation
naive_mappings_api
rml_mappings_api
```

## What is covered?

The initial documentation is organized around four sections:

- **Installation**: how to install the library and prepare the environment.
- **Quickstart**: a minimal example for generating RDF output.
- **ToposKG-core**: the main library concepts, objects, and parameters.
- **RDF generation**: how input data is transformed into RDF triples and proper configurations for the pipeline.

## Overview
*toposkg-lib* is a Python library developed as part of the *[Topos](https://toposkg.di.uoa.gr/)* framework. It provides easy access to powerful functionality for customizing and extending *[ToposKG](https://toposkg.di.uoa.gr/)* but is also compatible with arbitrary source files. 

## Highlights
- **Powerful features.** Customize and expand ToposKG using powerful tools for geospatial interlinking, toponym translation and entity linking. This specialy designed toolset leverages the high quality RDF data available with *ToposKG* to help users craft their own high quality geospatial knowledge graphs.
- **Ease of use.** toposkg-lib is designed around a simple builder pattern, simplifying the process of generating your Knowledge Graph.
- **Natural Language Interface.** toposkg-lib can be used with a textual interface, powered by LLM function calling.
- **Active development.** toposkg-lib will keep getting updates as we work on our projects.

## Repository contents
- `examples/`: Additional data, used in examples.
- `notebooks/`: Jupyter Notebooks that showcase the functionality of the library.
- `toposkg/`: The source code. Some files contain `main` functions that also include examples of use.
