# Developing AI-Ready Geospatial Knowledge Graphs with ToposKG and the Topos framework

In recent years, growing academic and industrial interest in geospatial artificial intelligence003
(GeoAI) has driven the construction of geospatial knowledge graphs (GeoKGs) using data
from a variety of sources. However, integrating
geospatial information into knowledge graphs
remains a complex challenge. Meanwhile, existing GeoKGs are either limited in scope or009
provide insufficient support for interoperability, integration with thematic knowledge, and011
topological consistency, limiting their reliability for downstream AI applications. In this013
paper, we present ToposKG, a comprehensive
GeoKG that integrates topologically consistent
administrative division data, general-purpose
geospatial information, and natural resource
data, including lakes, rivers, forests, and moun-
tains. ToposKG has been developed using the
Topos framework and its toolchain for inte-
grating both thematic and geospatial data into
knowledge graphs through interlinking. The
tools are made available via a Python library, a
desktop application, an MCP server and a digi-
tal assistant utilizing the MCP server. We also
evaluate the topological consistency of exist-
ing geospatial question-answering benchmarks
using ToposKG, investigating how incorrect
or unverifiable spatial relationships can affect
their reliability as resources for training and
evaluating AI systems.

## Contents

  - Topos-parser: The java project used to parse the various input sources and produce .ntriple files
  - kgui: ToposKG graphical user interface
  - toposkg_lib: The source code for the Topos
  - docs: Ontology file site
  - docker: A docker file to setup a GraphDB endpoint
  - stats: Statistics for ToposKG geospatial knowledge graph
  - topos-update-tool: Tool for automatically updating ToposKG with latest source data.
  - experiments: directory containing scripts and readmes for the benchmarking

Further instructions on how to build and use its separate project is present in each subdirectory.

## The ToposKG knowledge graph

ToposKG consists of various geospatial datasources including [OSM](https://www.openstreetmap.org/#map=7/52.716/-8.268), [GMBA](https://www.earthenv.org/mountains), [GAUL](https://www.fao.org/hih-geospatial-platform/news/detail/now-available--the-global-administrative-unit-layers-(gaul)-dataset---2024-edition/en) and [MarineRegions](https://www.marineregions.org/sources.php). Statistics of ToposKG are presented below:

| **Natural Resource** | **Data Source**   | **Number of Entities** | **Disk Footprint** |
|----------------------|-------------------|-------------------------|---------------------|
| Mountains            | GMBA              | 5,629                   | 201MB               |
| Water Bodies         | OSM               | 43,029,412              | 77GB                |
| Seas                 | MarineRegions     | 101                     | 339MB               |
| Forests              | OSM               | 21,239,112              | 49G                 |
| Administrative       | GAUL              | 48,316                  | 4.2GB               |
| Administrative       | OSM               | 1,583,535               | 25.3GB              |
| POIs                 | OSM               | 45,036,295              | 71GB                |
