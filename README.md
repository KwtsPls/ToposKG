# Developing geospatial knowledge graphs made simple with Topos and ToposKG

In recent years, growing academic and industrial interest has driven the
construction of geospatial knowledge graphs using data from a variety of
data sources. However, integrating geospatial information into knowledge graphs remains a complex challenge. Additionally, existing geospatial knowledge graphs are either limited in scope or provide insufficient support for interoperability and integration with thematic knowledge. In this paper, we present ToposKG, a comprehensive
geospatial knowledge graph that integrates topologically consistent
administrative division data, general purpose geospatial information, and natural resource data including lakes, rivers,
forests, and mountains. ToposKG has been developed using the Topos framework 
and its tool chain for integrating both thematic and geospatial data into knowledge graphs through interlinking. The tools are made available via a Python library, a desktop application, and a chatbot implemented through LLM function calling. We also present an evaluation of ToposKG, a qualitative comparison with existing geospatial knowledge graphs, and a demonstration of how our tool chain facilitated the construction of geospatial knowledge graphs for two real-world use cases.

## Contents

  - Topos-parser: The java project used to parse the various input sources and produce .ntriple files
  - kgui: ToposKG graphical user interface
  - toposkg_lib: The source code for the Topos [python library](https://pypi.org/project/toposkg/0.1.2/)

Further instructions on how to build and use its separate project is present in each subdirectory.

## The ToposKG knowledge graph

ToposKG consists of various geospatial datasources including [OSM](https://www.openstreetmap.org/#map=7/52.716/-8.268), [GMBA](https://www.earthenv.org/mountains), [GAUL](https://www.fao.org/hih-geospatial-platform/news/detail/now-available--the-global-administrative-unit-layers-(gaul)-dataset---2024-edition/en) and [MarineRegions](https://www.marineregions.org/sources.php). Statistics of ToposKG are presented below:

| **Natural Resource** | **Data Source**   | **Number of Entities** | **Disk Footprint** |
|----------------------|-------------------|-------------------------|---------------------|
| Mountains            | GMBA              | 5,629                   | 201MB               |
| Water Bodies         | OSM               | 20,426,694              | 34GB                |
| Seas                 | MarineRegions     | 101                     | 339MB               |
| Forests              | OSM               | 15,449,268              | 23G                 |
| Administrative       | GAUL              | 48,316                  | 4.2GB               |
| Administrative       | OSM               | 1,583,535               | 25.3GB              |
| POIs                 | OSM               | 43,885,054              | 14GB                |

The ToposKG knowledge graph is freely available in the official [site](https://toposkg.di.uoa.gr/)

## Team & Authors

<img align="right" src="https://github.com/AI-team-UoA/.github/blob/main/AI_LOGO.png?raw=true" alt="ai-team-uoa" width="200"/>

- [Kostas Plas](https://www.madgik.di.uoa.gr/el/people/msc-student/kplas), Research Associate at the University of Athens, Greece
- [Sergios-Anestis Kefalidis](http://users.uoa.gr/~skefalidis/), Research Associate at the University of Athens, Greece
- [Manolis Koubarakis](https://cgi.di.uoa.gr/~koubarak/), Professor at the University of Athens, Greece

This is a research project by the [AI-Team](https://ai.di.uoa.gr) of the Department of Informatics and Telecommunications at the University of Athens.
